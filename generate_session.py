"""
Telethon StringSession Generator for TGCloud Serverless and Cloud Deployments.

Run this script ONCE on your local terminal to log in to your Support Account:
    python generate_session.py

It will generate a single-line session string that you can paste directly into:
    TELEGRAM_STRING_SESSION="1BVts..."
in your TGCloud Environment Variables or .env file.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()


async def generate_string_session() -> None:
    print("=" * 65)
    print("  Telethon StringSession Generator for TGCloud Serverless")
    print("=" * 65)
    print("\nThis helper will authenticate your Support Account once and output")
    print("a portable StringSession for your TGCloud environment variables.\n")

    api_id_env = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash_env = os.getenv("TELEGRAM_API_HASH", "").strip()

    if api_id_env:
        api_id_str = input(f"Enter TELEGRAM_API_ID [{api_id_env}]: ").strip() or api_id_env
    else:
        api_id_str = input("Enter TELEGRAM_API_ID (from https://my.telegram.org): ").strip()

    if api_hash_env:
        api_hash = input(f"Enter TELEGRAM_API_HASH [{api_hash_env[:4]}...]: ").strip() or api_hash_env
    else:
        api_hash = input("Enter TELEGRAM_API_HASH (from https://my.telegram.org): ").strip()

    try:
        api_id = int(api_id_str)
    except ValueError:
        print("\n[Error] TELEGRAM_API_ID must be a numeric integer.")
        sys.exit(1)

    if not api_hash or len(api_hash) != 32:
        print("\n[Error] TELEGRAM_API_HASH must be a 32-character hexadecimal string.")
        sys.exit(1)

    print("\nConnecting to Telegram MTProto...")
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        phone = input("\nEnter Support Account Phone Number (with country code, e.g. +989123456789 or +14155552671): ").strip()
        await client.send_code_request(phone)
        code = input("Enter the login code sent to your Telegram app: ").strip()

        try:
            await client.sign_in(phone, code)
        except Exception as e:
            if "Two-steps verification" in str(e) or "SessionPasswordNeededError" in type(e).__name__:
                import getpass
                pwd = getpass.getpass("Enter your Two-Step Verification (2FA) password: ")
                await client.sign_in(password=pwd)
            else:
                print(f"\n[Login Failed] {str(e)}")
                sys.exit(1)

    me = await client.get_me()
    name = f"{me.first_name or ''} {me.last_name or ''}".strip()
    session_str = client.session.save()

    print("\n" + "=" * 65)
    print(f" SUCCESS! Authenticated as: {name} (User ID: {me.id})")
    print("=" * 65)
    print("\nCopy the following line and paste it into your TGCloud / .env file:")
    print("-" * 65)
    print(f"TELEGRAM_STRING_SESSION={session_str}")
    print("-" * 65)
    print("\n[SECURITY NOTICE]:")
    print("- Keep this session string completely private!")
    print("- Never commit this string to GitHub or send it to anyone.")
    print("- In TGCloud, add it in the 'Environment Variables' / 'Secrets' tab.\n")

    await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(generate_string_session())
    except KeyboardInterrupt:
        print("\nCancelled by user.")
