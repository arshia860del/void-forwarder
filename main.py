"""
Telegram Personal Support Notification System - Main Entry Point.

Listens for incoming private messages on the Support Account (Telethon MTProto)
and forwards formatted alerts in real-time to the operator's Main Account
via a dedicated Telegram Bot (Telegram Bot API).

Compatible with TGCloud Serverless, Docker containers, and standard Linux servers.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import signal
import sys
from typing import Optional

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User

from config import AppConfig, load_config
from dedup import DeduplicationCache
from formatter import analyze_media, format_support_notification
from bot_sender import BotNotificationSender

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("telegram_forwarder")


class SupportNotificationService:
    """Orchestrates Telethon listener and Bot API notification delivery."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.dedup = DeduplicationCache(
            max_size=config.dedup_cache_size,
            ttl_seconds=config.dedup_ttl_seconds,
        )
        self.bot_sender = BotNotificationSender(
            bot_token=config.notification_bot_token,
            main_account_id=config.main_account_id,
        )

        # Initialize Telethon client (StringSession for TGCloud/serverless or file session for VPS)
        if self.config.is_serverless:
            logger.info("Initializing Telethon with StringSession (Serverless/TGCloud mode)...")
            session = StringSession(self.config.string_session)
        else:
            logger.info(
                "Initializing Telethon with SQLite session file: '%s.session'...",
                self.config.session_name,
            )
            session = self.config.session_name

        self.client = TelegramClient(
            session=session,
            api_id=self.config.api_id,
            api_hash=self.config.api_hash,
            auto_reconnect=True,
            connection_retries=None,  # Infinite reconnection attempts on network drops
            retry_delay=2,
            timeout=15,
        )

        self._my_user_id: Optional[int] = None
        self._my_display_name: str = self.config.support_label
        self._startup_time: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
        self._is_running: bool = False

    async def _handle_new_message(self, event: events.NewMessage.Event) -> None:
        """
        Event listener triggered on any new message.
        Filters strictly for incoming private customer messages.
        """
        try:
            # 1. Reject outgoing messages (sent by the support account itself)
            if event.out:
                return

            # 2. Reject messages if sender is self
            sender_id = event.sender_id
            if sender_id is not None and sender_id == self._my_user_id:
                return

            # 3. Only process 1-on-1 private messages (no channels, groups, or supergroups)
            if not event.is_private:
                return

            # 4. Startup history protection: Ignore historical messages sent before service start
            msg_date = event.message.date
            if msg_date:
                if msg_date.tzinfo is None:
                    msg_date = msg_date.replace(tzinfo=datetime.timezone.utc)
                if msg_date < self._startup_time - datetime.timedelta(seconds=5):
                    logger.debug(
                        "Ignoring past message %s from sender %s (dated %s)",
                        event.message.id,
                        sender_id,
                        msg_date,
                    )
                    return

            # 5. Deduplication check: Avoid multiple notifications for the same message
            msg_id = event.message.id
            if sender_id is not None and self.dedup.is_duplicate(sender_id, msg_id):
                logger.debug(
                    "Duplicate message detected: sender=%s msg_id=%s. Skipping.",
                    sender_id,
                    msg_id,
                )
                return

            # 6. Extract sender profile information
            sender = await event.get_sender()
            sender_name = "Unknown Customer"
            sender_username = None

            if isinstance(sender, User):
                first_name = sender.first_name or ""
                last_name = sender.last_name or ""
                full_name = f"{first_name} {last_name}".strip()
                if full_name:
                    sender_name = full_name
                sender_username = sender.username
            elif sender and hasattr(sender, "title"):
                sender_name = str(sender.title)

            # 7. Analyze message content and media attachments
            media_type, media_desc = analyze_media(event.message)
            message_text = event.message.message or ""

            logger.info(
                "Incoming Support Message: from='%s' (@%s, ID=%s) type=%s length=%d",
                sender_name,
                sender_username or "none",
                sender_id,
                media_type,
                len(message_text),
            )

            # 8. Build formatted HTML notification
            notification_html = format_support_notification(
                sender_name=sender_name,
                sender_username=sender_username,
                sender_id=sender_id or 0,
                message_text=message_text,
                message_date=msg_date or datetime.datetime.now(datetime.timezone.utc),
                support_account_label=self._my_display_name,
                media_type=media_type,
                media_description=media_desc,
                timezone_str=self.config.timezone_str,
            )

            # 9. Deliver notification to operator's Main Account
            delivered = await self.bot_sender.send_notification(notification_html)
            if not delivered:
                logger.error(
                    "Failed to deliver notification for message %s from sender %s",
                    msg_id,
                    sender_id,
                )

        except Exception as e:
            logger.exception("Unexpected error in message handler: %s", str(e))

    async def start(self) -> None:
        """Start the Telethon client, verify accounts, and attach listeners."""
        logger.info("=" * 60)
        logger.info("Starting Telegram Support Notification System")
        logger.info("=" * 60)
        logger.info("\n%s\n", self.config.masked_summary())

        # 1. Verify Bot Token and connection to Telegram Bot API
        bot_check = await self.bot_sender.test_bot_credentials()
        if not bot_check.get("ok"):
            logger.error(
                "Aborting startup: Notification bot credentials could not be verified. "
                "Error: %s",
                bot_check.get("error"),
            )
            sys.exit(1)

        # 2. Start and authenticate Telethon Support Account client
        logger.info("Connecting to Telegram MTProto servers...")
        await self.client.connect()

        if not await self.client.is_user_authorized():
            if self.config.is_serverless:
                logger.critical(
                    "The provided TELEGRAM_STRING_SESSION is invalid or expired! "
                    "In serverless mode (TGCloud), you must generate a valid session string "
                    "using 'python generate_session.py' and set it in your environment."
                )
                sys.exit(1)
            else:
                logger.info(
                    "First-time interactive login required. Follow the prompt to log in..."
                )
                await self.client.start()

        # 3. Retrieve Support Account details
        me = await self.client.get_me()
        if not isinstance(me, User):
            logger.critical("Connected entity is not a Telegram user account!")
            sys.exit(1)

        self._my_user_id = me.id
        first_name = me.first_name or ""
        last_name = me.last_name or ""
        self._my_display_name = f"{first_name} {last_name}".strip() or self.config.support_label
        if me.username:
            self._my_display_name += f" (@{me.username})"

        logger.info(
            "Authenticated as Support Account: %s (ID: %s)",
            self._my_display_name,
            self._my_user_id,
        )

        # 4. Register event listener
        self.client.add_event_handler(
            self._handle_new_message,
            events.NewMessage(incoming=True, func=lambda e: e.is_private),
        )

        self._startup_time = datetime.datetime.now(datetime.timezone.utc)
        self._is_running = True

        logger.info("Event listener registered. Watching for incoming private customer messages.")

        # 5. Send startup confirmation ping to Main Account
        startup_msg = (
            "🚀 <b>Telegram Support Forwarder Active</b>\n\n"
            f"🟢 <b>Status:</b> Online &amp; Listening\n"
            f"👤 <b>Support Account:</b> {self._my_display_name}\n"
            f"🕒 <b>Started:</b> {self._startup_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"⚙️ <b>Mode:</b> {'TGCloud Serverless' if self.config.is_serverless else 'Container/Host'}\n\n"
            "All new customer messages will be delivered to this chat in real-time."
        )
        await self.bot_sender.send_notification(startup_msg)

    async def run_until_disconnected(self) -> None:
        """Run service loop until cancellation or disconnection."""
        try:
            await self.client.run_until_disconnected()
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Perform clean shutdown, close HTTP sessions, and disconnect client."""
        if not self._is_running:
            return
        self._is_running = False
        logger.info("Gracefully shutting down Telegram Support Forwarder...")

        try:
            await self.bot_sender.close()
        except Exception:
            pass

        try:
            if self.client.is_connected():
                await self.client.disconnect()
        except Exception:
            pass

        logger.info("Shutdown complete.")


def handle_signals(service: SupportNotificationService, loop: asyncio.AbstractEventLoop) -> None:
    """Attach graceful termination signals (SIGINT, SIGTERM)."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(service.shutdown()))
        except (NotImplementedError, RuntimeError):
            pass


async def main() -> None:
    """Application entry point."""
    try:
        config = load_config()
    except ValueError as val_err:
        logger.critical("\n[Configuration Error]\n%s\n", str(val_err))
        sys.exit(1)

    logging.getLogger().setLevel(getattr(logging, config.log_level, logging.INFO))
    service = SupportNotificationService(config)

    loop = asyncio.get_running_loop()
    handle_signals(service, loop)

    try:
        await service.start()
        await service.run_until_disconnected()
    except (asyncio.CancelledError, KeyboardInterrupt):
        await service.shutdown()
    except Exception as exc:
        logger.critical("Fatal error running service: %s", str(exc), exc_info=True)
        await service.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
