"""
Telegram User Account Client (MTProto via Telethon).
Enables broadcasting directly from a personal or business Telegram phone number
to recipient phone numbers without requiring recipients to click /start on a bot first.
"""
import asyncio
import logging
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.whatsapp_client import mask_phone_number

logger = logging.getLogger(__name__)


class TelegramUserAPIError(Exception):
    """Raised when Telegram MTProto client encounters an error."""
    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class TelegramUserClient:
    """
    Client for dispatching messages through a personal Telegram User Account.
    """

    def __init__(
        self,
        api_id: int | None = None,
        api_hash: str | None = None,
        session_name: str | None = None,
        dry_run: bool | None = None,
    ):
        self.api_id = api_id if api_id is not None else settings.TELEGRAM_API_ID
        self.api_hash = api_hash if api_hash is not None else settings.TELEGRAM_API_HASH
        self.session_name = session_name or settings.TELEGRAM_SESSION_NAME
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN

    def _get_session_path(self) -> Path:
        """Locates the .session file in the root workspace."""
        root_dir = Path(__file__).resolve().parent.parent.parent
        return root_dir / f"{self.session_name}.session"

    def is_session_authorized(self) -> bool:
        """Checks if a valid local .session file exists."""
        return self._get_session_path().exists()

    async def _send_async(
        self,
        to_phone: str,
        text: str,
        media_path: str | None = None,
    ) -> dict[str, Any]:
        """Asynchronous worker that connects to Telegram MTProto and delivers the message."""
        from telethon import TelegramClient as TelethonClient
        from telethon.errors import (
            PeerFloodError,
            UserPrivacyRestrictedError,
            FloodWaitError,
        )

        session_file = str(self._get_session_path().with_suffix(""))
        client = TelethonClient(session_file, self.api_id, self.api_hash)

        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise TelegramUserAPIError(
                    "Telegram session is not authorized. Run 'python scripts/login_telegram_user.py' once to log in."
                )

            # Resolve peer by phone number
            recipient = to_phone.strip()
            # If input is formatted like tg_12345, convert to integer chat id
            if recipient.startswith("tg_"):
                recipient = int(recipient.replace("tg_", ""))

            file_attachment = None
            if media_path and Path(media_path).exists():
                file_attachment = media_path

            sent_msg = await client.send_message(
                recipient,
                text,
                file=file_attachment,
            )

            msg_id = str(sent_msg.id)
            logger.info(f"Telegram user message {msg_id} sent to {mask_phone_number(str(to_phone))}")

            return {
                "dry_run": False,
                "provider": "telegram_user",
                "recipient": str(to_phone),
                "message_id": msg_id,
                "ok": True,
            }

        except FloodWaitError as exc:
            logger.error(f"Telegram FloodWaitError: Need to wait {exc.seconds}s.")
            raise TelegramUserAPIError(f"Rate limited by Telegram. Wait {exc.seconds}s.", exc)
        except PeerFloodError as exc:
            logger.error("Telegram PeerFloodError: Account temporarily restricted from messaging unknown users.")
            raise TelegramUserAPIError("Telegram spam limit reached (PeerFloodError). Add contact to phonebook first.", exc)
        except UserPrivacyRestrictedError as exc:
            logger.warning(f"User privacy settings restricted messaging {mask_phone_number(str(to_phone))}.")
            raise TelegramUserAPIError("User privacy settings restrict messages from unknown numbers.", exc)
        except Exception as exc:
            logger.error(f"Error sending Telegram user message: {exc}")
            raise TelegramUserAPIError(str(exc), exc)
        finally:
            await client.disconnect()

    def send_message(
        self,
        to_phone: str,
        text: str,
        media_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Sends a message to a recipient phone number from your personal Telegram account.
        In DRY_RUN mode, prints a simulation box without network requests.
        """
        masked = mask_phone_number(str(to_phone))

        # 1. DRY RUN (Simulation Mode)
        if self.dry_run:
            print("=" * 60)
            print(" [DRY RUN ACTIVE] Telegram User Account (Personal Phone) simulation")
            print("=" * 60)
            print(f" Sender Phone:    {settings.TELEGRAM_PHONE or 'Your Telegram Phone'}")
            print(f" Recipient Phone: {masked}")
            print(f" Message Text:    {text}")
            if media_path:
                print(f" Media File:      {media_path}")
            print(" Result:          Simulated success (no real Telegram call was made)")
            print("=" * 60)
            return {
                "dry_run": True,
                "provider": "telegram_user",
                "recipient": str(to_phone),
                "message_id": "simulated_tg_user_msg_id",
                "ok": True,
            }

        # 2. REAL SEND MODE
        if not self.api_id or not self.api_hash:
            raise TelegramUserAPIError(
                "TELEGRAM_API_ID and TELEGRAM_API_HASH are not set in .env. Obtain them from https://my.telegram.org."
            )

        if not self.is_session_authorized():
            raise TelegramUserAPIError(
                "Personal Telegram session not found. Please run 'python scripts/login_telegram_user.py' once to log in."
            )

        # Execute async call synchronously for the campaign dispatch loop
        try:
            return asyncio.run(self._send_async(to_phone, text, media_path))
        except RuntimeError:
            # Handle cases where an event loop is already running
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self._send_async(to_phone, text, media_path))
