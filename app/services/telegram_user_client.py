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

            # Resolve peer by phone number directly (no IDs needed)
            from telethon.tl.functions.contacts import ImportContactsRequest
            from telethon.tl.types import InputPhoneContact

            raw_recipient = str(to_phone).strip()
            target_peer = None

            if raw_recipient.startswith("tg_"):
                target_peer = int(raw_recipient.replace("tg_", ""))
            else:
                phone_digits = raw_recipient if raw_recipient.startswith("+") else f"+{raw_recipient}"
                try:
                    target_peer = await client.get_input_entity(phone_digits)
                except Exception:
                    # Import contact so Telegram MTProto can resolve the phone number
                    contact_req = InputPhoneContact(client_id=0, phone=phone_digits, first_name="Subscriber", last_name="")
                    imported = await client(ImportContactsRequest([contact_req]))
                    if imported.users:
                        target_peer = imported.users[0]
                    else:
                        raise TelegramUserAPIError(f"Phone number {phone_digits} is not registered on Telegram.")

            file_attachment = None
            if media_path and Path(media_path).exists():
                file_attachment = media_path

            sent_msg = await client.send_message(
                target_peer,
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

    def _validate_ready(self) -> None:
        """Validates that MTProto API credentials and an authorized session file exist."""
        if not self.api_id or not self.api_hash:
            raise TelegramUserAPIError(
                "TELEGRAM_API_ID and TELEGRAM_API_HASH are not set in .env. Obtain them from https://my.telegram.org."
            )

        if not self.is_session_authorized():
            raise TelegramUserAPIError(
                "Personal Telegram session not found. Please run 'python scripts/login_telegram_user.py' once to log in."
            )

    async def send_message_async(
        self,
        to_phone: str,
        text: str,
        media_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Asynchronously sends a message to a recipient phone number from your personal Telegram account.
        In DRY_RUN mode, returns simulated success without network requests.
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
        self._validate_ready()
        return await self._send_async(to_phone, text, media_path)

    def send_message(
        self,
        to_phone: str,
        text: str,
        media_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Synchronously sends a message to a recipient phone number from your personal Telegram account.
        Safe to call from both synchronous code and active event loop threads.
        """
        if self.dry_run:
            # Short-circuit dry-run without loop management
            masked = mask_phone_number(str(to_phone))
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
        self._validate_ready()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self._send_async(to_phone, text, media_path)).result()
        else:
            return asyncio.run(self._send_async(to_phone, text, media_path))
