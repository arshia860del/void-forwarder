"""
Message formatting and media analyzer for Telegram Support Notifications.

Handles:
- Safe HTML escaping (prevents Telegram parse entity errors)
- Text and non-text messages (photos, videos, voice notes, stickers, docs)
- Timezone localization (e.g. Asia/Tehran, Europe/London, UTC)
- Fallback for missing usernames
"""

from __future__ import annotations

import html
import datetime
from typing import Any, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

try:
    import pytz
except ImportError:
    pytz = None  # type: ignore


def escape_html(text: Optional[str]) -> str:
    """Safely escape HTML entities for Telegram Bot API parse_mode='HTML'."""
    if not text:
        return ""
    return html.escape(str(text), quote=False)


def format_bytes(size_bytes: Optional[int]) -> str:
    """Format bytes into human-readable size (e.g., 1.4 MB)."""
    if not size_bytes or size_bytes <= 0:
        return "Unknown size"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def format_duration(seconds: Optional[int]) -> str:
    """Format seconds into M:SS or H:MM:SS."""
    if not seconds:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def analyze_media(message: Any) -> tuple[str, str]:
    """Examine a Telethon message to determine its media category and rich description."""
    if getattr(message, "photo", None):
        return "Photo", "📷 Photo image"

    if getattr(message, "voice", None):
        duration = 0
        mime = "audio/ogg"
        if getattr(message, "document", None) and hasattr(message.document, "attributes"):
            for attr in message.document.attributes:
                if hasattr(attr, "duration"):
                    duration = attr.duration
            mime = getattr(message.document, "mime_type", mime)
        dur_str = format_duration(duration)
        return "Voice Note", f"🎤 Voice message ({dur_str}, {mime})"

    if getattr(message, "video_note", None):
        duration = 0
        if getattr(message, "document", None) and hasattr(message.document, "attributes"):
            for attr in message.document.attributes:
                if hasattr(attr, "duration"):
                    duration = attr.duration
        dur_str = format_duration(duration)
        return "Video Note", f"⭕ Round video note ({dur_str})"

    if getattr(message, "video", None):
        duration = 0
        w, h = 0, 0
        size_bytes = getattr(message.document, "size", 0) if getattr(message, "document", None) else 0
        if getattr(message, "document", None) and hasattr(message.document, "attributes"):
            for attr in message.document.attributes:
                if hasattr(attr, "duration"):
                    duration = attr.duration
                if hasattr(attr, "w") and hasattr(attr, "h"):
                    w, h = attr.w, attr.h
        dur_str = format_duration(duration)
        dim_str = f", {w}x{h}" if w and h else ""
        return "Video", f"🎬 Video ({dur_str}{dim_str}, {format_bytes(size_bytes)})"

    if getattr(message, "audio", None):
        duration = 0
        title = "Audio file"
        performer = ""
        size_bytes = getattr(message.document, "size", 0) if getattr(message, "document", None) else 0
        if getattr(message, "document", None) and hasattr(message.document, "attributes"):
            for attr in message.document.attributes:
                if hasattr(attr, "duration"):
                    duration = attr.duration
                if hasattr(attr, "title") and attr.title:
                    title = attr.title
                if hasattr(attr, "performer") and attr.performer:
                    performer = f" by {attr.performer}"
        return "Audio", f"🎵 {title}{performer} ({format_duration(duration)}, {format_bytes(size_bytes)})"

    if getattr(message, "sticker", None):
        alt = ""
        if getattr(message, "document", None) and hasattr(message.document, "attributes"):
            for attr in message.document.attributes:
                if hasattr(attr, "alt"):
                    alt = f" (emoji: {attr.alt})"
        return "Sticker", f"🎭 Sticker{alt}"

    if getattr(message, "document", None):
        doc = message.document
        filename = "document"
        if hasattr(doc, "attributes"):
            for attr in doc.attributes:
                if hasattr(attr, "file_name") and attr.file_name:
                    filename = attr.file_name
                    break
        size = format_bytes(getattr(doc, "size", 0))
        mime = getattr(doc, "mime_type", "application/octet-stream")
        return "Document", f"📄 File: {filename} ({size}, {mime})"

    if getattr(message, "contact", None):
        c = message.contact
        phone = getattr(c, "phone_number", "Hidden")
        name = f"{getattr(c, 'first_name', '')} {getattr(c, 'last_name', '')}".strip()
        return "Contact", f"👤 Shared Contact: {name} (Phone: {phone})"

    if getattr(message, "geo", None):
        g = message.geo
        lat = getattr(g, "lat", 0.0)
        long = getattr(g, "long", 0.0)
        return "Location", f"📍 Location coordinates: {lat:.6f}, {long:.6f}"

    if getattr(message, "poll", None):
        question = getattr(message.poll.poll, "question", "Poll")
        return "Poll", f"📊 Poll: {question}"

    if getattr(message, "message", None):
        return "Text", "Plain text message"

    return "Other", "Non-text Telegram message"


def format_support_notification(
    sender_name: str,
    sender_username: Optional[str],
    sender_id: int,
    message_text: Optional[str],
    message_date: datetime.datetime,
    support_account_label: str = "Support Account",
    media_type: str = "Text",
    media_description: str = "",
    timezone_str: str = "UTC",
) -> str:
    """Build the formatted notification text formatted in clean HTML for Telegram Bot API."""
    local_time = message_date
    try:
        if ZoneInfo:
            target_tz = ZoneInfo(timezone_str)
            if message_date.tzinfo is None:
                message_date = message_date.replace(tzinfo=datetime.timezone.utc)
            local_time = message_date.astimezone(target_tz)
        elif pytz:
            tz = pytz.timezone(timezone_str)
            if message_date.tzinfo is None:
                message_date = pytz.utc.localize(message_date)
            local_time = message_date.astimezone(tz)
    except Exception:
        local_time = message_date

    time_str = local_time.strftime("%Y-%m-%d %H:%M:%S")

    clean_name = escape_html(sender_name.strip() or "Unnamed User")
    user_id_str = str(sender_id)

    if sender_username:
        clean_user = f"@{escape_html(sender_username.lstrip('@'))}"
        username_line = f"🔗 <b>Username:</b> {clean_user}\n"
    else:
        username_line = "🔗 <b>Username:</b> <i>Not available</i>\n"

    content_lines: list[str] = []

    if media_type != "Text":
        content_lines.append(f"📎 <b>Attachment:</b> {escape_html(media_description)}")

    if message_text and message_text.strip():
        label = "💬 <b>Caption:</b>" if media_type != "Text" else "💬 <b>Message:</b>"
        clean_body = escape_html(message_text.strip())
        content_lines.append(f"{label}\n{clean_body}")
    elif media_type == "Text":
        content_lines.append("💬 <b>Message:</b>\n<i>[Empty message]</i>")

    body_block = "\n\n".join(content_lines)

    notification = (
        "📩 <b>NEW SUPPORT MESSAGE</b>\n\n"
        f"👤 <b>Name:</b> {clean_name}\n"
        f"{username_line}"
        f"🆔 <b>User ID:</b> <code>{user_id_str}</code>\n\n"
        f"{body_block}\n\n"
        f"🕒 <b>Time:</b> {time_str} ({escape_html(timezone_str)})\n"
        f"📨 <b>Received by:</b> {escape_html(support_account_label)}"
    )

    return notification
