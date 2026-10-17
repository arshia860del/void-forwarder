"""
Configuration management for the Telegram Support Notification System.

Supports both:
1. Serverless/TGCloud environments using TELEGRAM_STRING_SESSION
2. Traditional container/VPS environments using SQLite session files
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration with strict validation."""

    api_id: int
    api_hash: str
    notification_bot_token: str
    main_account_id: int
    string_session: Optional[str] = None
    session_name: str = "support_account"
    timezone_str: str = "UTC"
    support_label: str = "Support Account"
    dedup_cache_size: int = 2000
    dedup_ttl_seconds: int = 3600
    log_level: str = "INFO"

    @property
    def is_serverless(self) -> bool:
        """Returns True if running in serverless mode (using StringSession)."""
        return bool(self.string_session and self.string_session.strip())

    def masked_summary(self) -> str:
        """Return a safe summary of configuration without revealing secrets."""
        bot_prefix = (
            self.notification_bot_token.split(":")[0]
            if ":" in self.notification_bot_token
            else "***"
        )
        mode = "TGCloud Serverless (StringSession)" if self.is_serverless else f"File Session ({self.session_name}.session)"
        return (
            f"Mode: {mode}\n"
            f"Telegram API ID: {self.api_id}\n"
            f"API Hash: {self.api_hash[:4]}...{self.api_hash[-4:]}\n"
            f"Bot Token: {bot_prefix}:********************\n"
            f"Main Account ID: {self.main_account_id}\n"
            f"Timezone: {self.timezone_str}\n"
            f"Support Label: {self.support_label}"
        )


def load_config() -> AppConfig:
    """Validate and return the application configuration."""
    errors: list[str] = []

    # 1. TELEGRAM_API_ID
    raw_api_id = os.getenv("TELEGRAM_API_ID", "").strip()
    api_id = 0
    if not raw_api_id:
        errors.append("TELEGRAM_API_ID is required. Obtain it from https://my.telegram.org")
    else:
        try:
            api_id = int(raw_api_id)
            if api_id <= 0:
                errors.append("TELEGRAM_API_ID must be a positive integer.")
        except ValueError:
            errors.append("TELEGRAM_API_ID must be a numeric integer.")

    # 2. TELEGRAM_API_HASH
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    if not api_hash:
        errors.append("TELEGRAM_API_HASH is required. Obtain it from https://my.telegram.org")
    elif len(api_hash) != 32 or not re.match(r"^[0-9a-fA-F]{32}$", api_hash):
        errors.append("TELEGRAM_API_HASH must be a 32-character hexadecimal string.")

    # 3. NOTIFICATION_BOT_TOKEN
    bot_token = os.getenv("NOTIFICATION_BOT_TOKEN", "").strip()
    if not bot_token:
        errors.append("NOTIFICATION_BOT_TOKEN is required. Obtain it from @BotFather on Telegram.")
    elif not re.match(r"^\d{6,15}:[A-Za-z0-9_-]{25,}$", bot_token):
        errors.append(
            "NOTIFICATION_BOT_TOKEN format is invalid. "
            "Expected format: 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ (from @BotFather)"
        )

    # 4. MAIN_ACCOUNT_ID
    raw_main_id = os.getenv("MAIN_ACCOUNT_ID", "").strip()
    main_account_id = 0
    if not raw_main_id:
        errors.append(
            "MAIN_ACCOUNT_ID is required. This is your personal Telegram numeric user ID "
            "(obtain it from @userinfobot or @raw_data_bot on Telegram)."
        )
    else:
        try:
            main_account_id = int(raw_main_id)
            if main_account_id <= 0:
                errors.append("MAIN_ACCOUNT_ID must be a positive integer.")
        except ValueError:
            errors.append("MAIN_ACCOUNT_ID must be a numeric integer.")

    # 5. Session String / Session File
    string_session = os.getenv("TELEGRAM_STRING_SESSION") or os.getenv("TGCLOUD_SESSION")
    if string_session:
        string_session = string_session.strip()

    session_name = os.getenv("SUPPORT_SESSION_NAME", "support_account").strip() or "support_account"
    timezone_str = os.getenv("TIMEZONE", "UTC").strip() or "UTC"
    support_label = os.getenv("SUPPORT_ACCOUNT_LABEL", "Support Account").strip() or "Support Account"

    try:
        dedup_cache_size = int(os.getenv("DEDUP_CACHE_SIZE", "2000"))
    except ValueError:
        dedup_cache_size = 2000

    try:
        dedup_ttl_seconds = int(os.getenv("DEDUP_TTL_SECONDS", "3600"))
    except ValueError:
        dedup_ttl_seconds = 3600

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    if errors:
        error_msg = "Configuration Validation Failed:\n" + "\n".join(f" - {e}" for e in errors)
        raise ValueError(error_msg)

    return AppConfig(
        api_id=api_id,
        api_hash=api_hash,
        notification_bot_token=bot_token,
        main_account_id=main_account_id,
        string_session=string_session,
        session_name=session_name,
        timezone_str=timezone_str,
        support_label=support_label,
        dedup_cache_size=dedup_cache_size,
        dedup_ttl_seconds=dedup_ttl_seconds,
        log_level=log_level,
    )
