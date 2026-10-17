"""
Telegram Bot API notification sender.
Handles delivery of notifications to the main Telegram account with:
- Retry with exponential backoff
- Telegram FloodWait (429) rate limit handling
- Secret masking in all log messages
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional
import aiohttp

logger = logging.getLogger("telegram_forwarder.bot_sender")


class BotNotificationSender:
    """Delivers support notifications to the main user via Telegram Bot API."""

    def __init__(self, bot_token: str, main_account_id: int):
        self._bot_token = bot_token
        self.main_account_id = main_account_id
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._session: Optional[aiohttp.ClientSession] = None

        parts = bot_token.split(":")
        self._masked_token = f"{parts[0]}:***" if len(parts) == 2 else "***"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=20)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close underlying HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def test_bot_credentials(self) -> dict:
        """Verify that the notification bot token is valid and responsive."""
        session = await self._get_session()
        url = f"{self._base_url}/getMe"
        try:
            async with session.get(url) as resp:
                data = await resp.json()
                if resp.status == 200 and data.get("ok"):
                    bot_info = data.get("result", {})
                    logger.info(
                        "Notification Bot verified successfully: @%s (ID: %s)",
                        bot_info.get("username"),
                        bot_info.get("id"),
                    )
                    return {"ok": True, "result": bot_info}
                else:
                    description = data.get("description", "Unknown error")
                    logger.error("Bot verification failed: %s", description)
                    return {"ok": False, "error": description}
        except Exception as e:
            logger.error("Network error while verifying bot: %s", str(e))
            return {"ok": False, "error": str(e)}

    async def send_notification(
        self,
        html_text: str,
        max_retries: int = 3,
    ) -> bool:
        """Send formatted HTML message to the main account with automatic retry."""
        session = await self._get_session()
        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": self.main_account_id,
            "text": html_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        attempt = 0
        backoff = 1.5

        while attempt < max_retries:
            attempt += 1
            try:
                async with session.post(url, json=payload) as resp:
                    data = await resp.json()

                    if resp.status == 200 and data.get("ok"):
                        logger.info(
                            "Notification successfully delivered to Main Account %s (Message ID: %s)",
                            self.main_account_id,
                            data.get("result", {}).get("message_id"),
                        )
                        return True

                    if resp.status == 429:
                        parameters = data.get("parameters", {})
                        retry_after = parameters.get("retry_after", 5)
                        logger.warning(
                            "Telegram Bot API rate limit reached (FloodWait). Sleeping for %s seconds (Attempt %s/%s)",
                            retry_after,
                            attempt,
                            max_retries,
                        )
                        await asyncio.sleep(retry_after + 1)
                        continue

                    if resp.status == 403:
                        logger.error(
                            "Delivery Failed (403 Forbidden): The main account %s has not started the bot yet! "
                            "Action required: Open Telegram, search for your bot, and send /start to it.",
                            self.main_account_id,
                        )
                        return False

                    if resp.status == 400:
                        desc = data.get("description", "")
                        logger.error("Delivery Failed (400 Bad Request): %s", desc)
                        return False

                    logger.warning(
                        "Telegram Bot API returned HTTP %s on attempt %s/%s: %s",
                        resp.status,
                        attempt,
                        max_retries,
                        data.get("description", ""),
                    )

            except (aiohttp.ClientError, asyncio.TimeoutError) as net_err:
                logger.warning(
                    "Network error delivering notification (Attempt %s/%s): %s",
                    attempt,
                    max_retries,
                    str(net_err),
                )

            if attempt < max_retries:
                await asyncio.sleep(backoff)
                backoff *= 2

        logger.error(
            "Exhausted all %s delivery attempts for notification to %s",
            max_retries,
            self.main_account_id,
        )
        return False
