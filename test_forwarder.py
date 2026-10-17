"""
Test suite for the Telegram Support Notification System.

Run tests with:
    python test_forwarder.py
"""

from __future__ import annotations

import datetime
import os
import unittest
from unittest.mock import MagicMock

from config import AppConfig, load_config
from dedup import DeduplicationCache
from formatter import (
    analyze_media,
    escape_html,
    format_bytes,
    format_duration,
    format_support_notification,
)


class TestConfigValidation(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_missing_required_variables(self):
        os.environ.clear()
        with self.assertRaises(ValueError) as ctx:
            load_config()
        msg = str(ctx.exception)
        self.assertIn("TELEGRAM_API_ID is required", msg)
        self.assertIn("TELEGRAM_API_HASH is required", msg)
        self.assertIn("NOTIFICATION_BOT_TOKEN is required", msg)
        self.assertIn("MAIN_ACCOUNT_ID is required", msg)

    def test_invalid_api_hash_format(self):
        os.environ["TELEGRAM_API_ID"] = "123456"
        os.environ["TELEGRAM_API_HASH"] = "invalid_short_hash"
        os.environ["NOTIFICATION_BOT_TOKEN"] = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ0123456"
        os.environ["MAIN_ACCOUNT_ID"] = "987654321"

        with self.assertRaises(ValueError) as ctx:
            load_config()
        self.assertIn("32-character hexadecimal", str(ctx.exception))

    def test_valid_configuration_and_serverless_flag(self):
        os.environ["TELEGRAM_API_ID"] = "123456"
        os.environ["TELEGRAM_API_HASH"] = "0123456789abcdef0123456789abcdef"
        os.environ["NOTIFICATION_BOT_TOKEN"] = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ0123456"
        os.environ["MAIN_ACCOUNT_ID"] = "987654321"
        os.environ["TELEGRAM_STRING_SESSION"] = "1BVtsOxxxxSampleSessionString..."

        config = load_config()
        self.assertEqual(config.api_id, 123456)
        self.assertTrue(config.is_serverless)
        self.assertIn("TGCloud Serverless", config.masked_summary())
        self.assertNotIn("0123456789abcdef0123456789abcdef", config.masked_summary())


class TestDeduplicationCache(unittest.TestCase):
    def test_duplicate_detection(self):
        cache = DeduplicationCache(max_size=10, ttl_seconds=60)
        self.assertFalse(cache.is_duplicate(111, 999))
        self.assertTrue(cache.is_duplicate(111, 999))

    def test_lru_capacity_eviction(self):
        cache = DeduplicationCache(max_size=3, ttl_seconds=300)
        cache.is_duplicate(1, 101)
        cache.is_duplicate(1, 102)
        cache.is_duplicate(1, 103)
        self.assertEqual(cache.size(), 3)
        cache.is_duplicate(1, 104)
        self.assertEqual(cache.size(), 3)
        self.assertFalse(cache.is_duplicate(1, 101))


class TestFormatter(unittest.TestCase):
    def test_html_escaping_prevents_xss(self):
        raw_text = '<script>alert("xss")</script> & "special"'
        escaped = escape_html(raw_text)
        self.assertNotIn("<script>", escaped)
        self.assertIn("&lt;script&gt;", escaped)
        self.assertIn("&amp;", escaped)

    def test_format_notification_with_username(self):
        dt = datetime.datetime(2026, 10, 15, 18, 42, 0, tzinfo=datetime.timezone.utc)
        result = format_support_notification(
            sender_name="John Doe",
            sender_username="johndoe",
            sender_id=123456789,
            message_text="Hello, I need help with my order.",
            message_date=dt,
            support_account_label="Support Dept",
            media_type="Text",
            timezone_str="UTC",
        )
        self.assertIn("📩 <b>NEW SUPPORT MESSAGE</b>", result)
        self.assertIn("👤 <b>Name:</b> John Doe", result)
        self.assertIn("🔗 <b>Username:</b> @johndoe", result)
        self.assertIn("🆔 <b>User ID:</b> <code>123456789</code>", result)
        self.assertIn("Hello, I need help with my order.", result)
        self.assertIn("2026-10-15 18:42:00 (UTC)", result)
        self.assertIn("📨 <b>Received by:</b> Support Dept", result)

    def test_format_notification_without_username(self):
        dt = datetime.datetime(2026, 10, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = format_support_notification(
            sender_name="Anonymous Customer",
            sender_username=None,
            sender_id=555666777,
            message_text="No username account",
            message_date=dt,
            support_account_label="Support Account",
            media_type="Text",
        )
        self.assertIn("<i>Not available</i>", result)
        self.assertIn("555666777", result)


if __name__ == "__main__":
    unittest.main()
