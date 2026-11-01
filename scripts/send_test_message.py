"""
CLI script to send the 'hello_world' WhatsApp template to a test phone number.

Usage:
    # Using command-line argument:
    python scripts/send_test_message.py --phone "+919876543210"

    # Interactive prompt:
    python scripts/send_test_message.py
"""
import argparse
import sys
from pathlib import Path

# Ensure the root project directory is on sys.path so 'app' imports work seamlessly
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.services.whatsapp_client import WhatsAppClient, WhatsAppAPIError, mask_phone_number


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send the official WhatsApp 'hello_world' template message to a test recipient."
    )
    parser.add_argument(
        "--phone",
        type=str,
        help="Recipient phone number in E.164 format (e.g. +919876543210)",
    )
    args = parser.parse_args()

    phone = args.phone
    if not phone:
        print("\n--- WhatsApp Broadcaster: Test Sender ---")
        phone = input("Enter your recipient phone number (e.g. +919876543210): ").strip()

    if not phone:
        print("Error: Phone number cannot be empty.", file=sys.stderr)
        sys.exit(1)

    print(f"\nTarget Recipient: {mask_phone_number(phone)}")
    print(f"Current Mode:     {'DRY RUN (Simulation)' if settings.DRY_RUN else 'LIVE SEND'}")

    client = WhatsAppClient()

    try:
        result = client.send_template(to_phone=phone, template_name="hello_world")
        print("\n[SUCCESS] Operation completed successfully!")
        if result.get("dry_run"):
            print("\nTip: To perform a real WhatsApp send to your phone:")
            print("  1. Update .env with your real WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID from Meta.")
            print("  2. In your Meta Dashboard, ensure this recipient number is added to 'Manage phone number list'.")
            print("  3. Set DRY_RUN=false in .env.")
            print("  4. Re-run this script!\n")
        else:
            messages = result.get("messages", [])
            wamid = messages[0].get("id") if messages else "N/A"
            print(f"Message ID: {wamid}")
            print("Check WhatsApp on your test phone to see the incoming message!\n")

    except ValueError as exc:
        print(f"\n[CONFIGURATION ERROR]: {exc}", file=sys.stderr)
        sys.exit(1)
    except WhatsAppAPIError as exc:
        print(f"\n[API ERROR]:\n{exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[UNEXPECTED ERROR]: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
