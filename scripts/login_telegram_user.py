"""
One-Time Telegram User Account Authentication Script.
Logs into your personal or business Telegram account and generates
a secure local 'telegram_user.session' file for automated broadcasting.
"""
import sys
from pathlib import Path

# Ensure UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from telethon.sync import TelegramClient
from app.config import settings


def main() -> None:
    print("=" * 65)
    print(" 🔐 Telegram Personal Account One-Time Login")
    print("=" * 65)
    print("This script connects your personal Telegram number so you can broadcast")
    print("directly to recipient phone numbers without requiring bot links.")
    print("=" * 65)

    api_id = settings.TELEGRAM_API_ID
    api_hash = settings.TELEGRAM_API_HASH
    phone = settings.TELEGRAM_PHONE

    if not api_id or not api_hash:
        print("\n⚠️ TELEGRAM_API_ID or TELEGRAM_API_HASH is not set in .env.")
        try:
            api_id_input = input("Enter your Telegram App API ID: ").strip()
            api_id = int(api_id_input)
            api_hash = input("Enter your Telegram App API Hash: ").strip()
        except Exception:
            print("❌ Invalid input. Exiting.")
            sys.exit(1)

    if not phone:
        phone = input("\nEnter your Telegram mobile number (with country code, e.g. +919876543210): ").strip()

    session_path = ROOT_DIR / settings.TELEGRAM_SESSION_NAME
    print(f"\nConnecting to Telegram servers using session '{settings.TELEGRAM_SESSION_NAME}'...")

    client = TelegramClient(str(session_path), api_id, api_hash)
    client.start(phone=phone)

    me = client.get_me()
    print("\n" + "=" * 65)
    print(" ✅ Successfully Authenticated!")
    print(f" • Logged in as: {me.first_name} {me.last_name or ''} (@{me.username or 'No username'})")
    print(f" • Phone Number: +{me.phone}")
    print(f" • Session File: {session_path}.session (Saved securely locally)")
    print("=" * 65)
    print("You can now broadcast messages and media directly from this number!")
    print("=" * 65)
    client.disconnect()


if __name__ == "__main__":
    main()
