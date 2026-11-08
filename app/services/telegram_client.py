"""
Telegram Bot API client.
Handles outbound messaging, dry-run simulations, and webhook management.
Follows the same interface conventions as WhatsAppClient for multi-channel support.
"""
import logging
from pathlib import Path
from typing import Any
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class TelegramAPIError(Exception):
    """Raised when the Telegram Bot API returns an error response."""
    def __init__(self, message: str, status_code: int | None = None, error_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


def mask_chat_id(chat_id: str | int) -> str:
    """
    Masks a Telegram chat ID or phone number to protect customer privacy in logs.
    Example: '123456789' -> '12****89'
    """
    s = str(chat_id).strip()
    if len(s) < 5:
        return "****"
    return f"{s[:2]}****{s[-2:]}"


class TelegramClient:
    """
    Client for interacting with the official Telegram Bot API.
    """

    def __init__(
        self,
        bot_token: str | None = None,
        dry_run: bool | None = None,
    ):
        self.bot_token = bot_token if bot_token is not None else settings.TELEGRAM_BOT_TOKEN
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN

    @property
    def base_url(self) -> str:
        """Constructs the base URL for the bot API."""
        return f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(
        self,
        chat_id: str | int,
        text: str,
        parse_mode: str = "HTML",
    ) -> dict[str, Any]:
        """
        Sends a message to a specific Telegram chat/user.
        In DRY_RUN mode, logs the dispatch without making an external HTTP call.
        """
        chat_id_str = str(chat_id).strip()
        masked_id = mask_chat_id(chat_id_str)

        # 1. DRY RUN (Simulation Mode)
        if self.dry_run:
            print("=" * 60)
            print(" [DRY RUN ACTIVE] Telegram message send simulation")
            print("=" * 60)
            print(f" Recipient Chat ID: {masked_id}")
            print(f" Text:              {text}")
            print(" Result:            Simulated success (no real HTTP call was made)")
            print("=" * 60)
            return {
                "dry_run": True,
                "provider": "telegram",
                "chat_id": chat_id_str,
                "message_id": "simulated_tg_wamid",
                "ok": True,
            }

        # 2. REAL SEND MODE
        if not self.bot_token or self.bot_token == "your_telegram_bot_token_from_botfather":
            raise TelegramAPIError("TELEGRAM_BOT_TOKEN is not configured in environment.")

        endpoint = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id_str,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(endpoint, json=payload)
                data = response.json()

                if not response.is_success or not data.get("ok"):
                    error_desc = data.get("description", response.text)
                    error_code = data.get("error_code", response.status_code)
                    logger.error(
                        f"Telegram API error {error_code} sending to {masked_id}: {error_desc}"
                    )
                    raise TelegramAPIError(
                        message=f"Telegram API error: {error_desc}",
                        status_code=response.status_code,
                        error_code=error_code,
                    )

                result = data.get("result", {})
                message_id = str(result.get("message_id", ""))
                logger.info(f"Telegram message {message_id} sent to {masked_id}")

                return {
                    "dry_run": False,
                    "provider": "telegram",
                    "chat_id": chat_id_str,
                    "message_id": message_id,
                    "ok": True,
                    "raw": data,
                }

        except httpx.RequestError as exc:
            logger.error(f"Network error connecting to Telegram API: {exc}")
            raise TelegramAPIError(f"Network error: {str(exc)}")

    def send_photo(
        self,
        chat_id: str | int,
        photo: str,
        caption: str | None = None,
        parse_mode: str = "HTML",
    ) -> dict[str, Any]:
        """
        Sends a photo with optional caption to a Telegram chat.
        'photo' can be a public URL or a local file path.
        """
        chat_id_str = str(chat_id).strip()
        masked_id = mask_chat_id(chat_id_str)

        if self.dry_run:
            print("=" * 60)
            print(" [DRY RUN ACTIVE] Telegram photo send simulation")
            print("=" * 60)
            print(f" Recipient Chat ID: {masked_id}")
            print(f" Photo:             {photo}")
            print(f" Caption:           {caption}")
            print(" Result:            Simulated success (no real HTTP call was made)")
            print("=" * 60)
            return {
                "dry_run": True,
                "provider": "telegram",
                "chat_id": chat_id_str,
                "message_id": "simulated_tg_photo_id",
                "ok": True,
            }

        if not self.bot_token or self.bot_token == "your_telegram_bot_token_from_botfather":
            raise TelegramAPIError("TELEGRAM_BOT_TOKEN is not configured in environment.")

        endpoint = f"{self.base_url}/sendPhoto"
        is_url = photo.startswith("http://") or photo.startswith("https://")

        try:
            with httpx.Client(timeout=25.0) as client:
                if is_url:
                    payload = {
                        "chat_id": chat_id_str,
                        "photo": photo,
                        "caption": caption or "",
                        "parse_mode": parse_mode,
                    }
                    response = client.post(endpoint, json=payload)
                else:
                    file_path = Path(photo)
                    if not file_path.exists():
                        raise TelegramAPIError(f"Local photo file not found: {photo}")
                    with open(file_path, "rb") as f:
                        response = client.post(
                            endpoint,
                            data={"chat_id": chat_id_str, "caption": caption or "", "parse_mode": parse_mode},
                            files={"photo": (file_path.name, f.read())},
                        )

                data = response.json()
                if not response.is_success or not data.get("ok"):
                    error_desc = data.get("description", response.text)
                    error_code = data.get("error_code", response.status_code)
                    raise TelegramAPIError(f"Telegram API error: {error_desc}", response.status_code, error_code)

                result = data.get("result", {})
                message_id = str(result.get("message_id", ""))
                return {"dry_run": False, "provider": "telegram", "chat_id": chat_id_str, "message_id": message_id, "ok": True}
        except httpx.RequestError as exc:
            raise TelegramAPIError(f"Network error: {str(exc)}")

    def send_video(
        self,
        chat_id: str | int,
        video: str,
        caption: str | None = None,
        parse_mode: str = "HTML",
    ) -> dict[str, Any]:
        """
        Sends a video with optional caption to a Telegram chat.
        'video' can be a public URL or a local file path.
        """
        chat_id_str = str(chat_id).strip()
        masked_id = mask_chat_id(chat_id_str)

        if self.dry_run:
            print("=" * 60)
            print(" [DRY RUN ACTIVE] Telegram video send simulation")
            print("=" * 60)
            print(f" Recipient Chat ID: {masked_id}")
            print(f" Video:             {video}")
            print(f" Caption:           {caption}")
            print(" Result:            Simulated success (no real HTTP call was made)")
            print("=" * 60)
            return {
                "dry_run": True,
                "provider": "telegram",
                "chat_id": chat_id_str,
                "message_id": "simulated_tg_video_id",
                "ok": True,
            }

        if not self.bot_token or self.bot_token == "your_telegram_bot_token_from_botfather":
            raise TelegramAPIError("TELEGRAM_BOT_TOKEN is not configured in environment.")

        endpoint = f"{self.base_url}/sendVideo"
        is_url = video.startswith("http://") or video.startswith("https://")

        try:
            with httpx.Client(timeout=35.0) as client:
                if is_url:
                    payload = {
                        "chat_id": chat_id_str,
                        "video": video,
                        "caption": caption or "",
                        "parse_mode": parse_mode,
                    }
                    response = client.post(endpoint, json=payload)
                else:
                    file_path = Path(video)
                    if not file_path.exists():
                        raise TelegramAPIError(f"Local video file not found: {video}")
                    with open(file_path, "rb") as f:
                        response = client.post(
                            endpoint,
                            data={"chat_id": chat_id_str, "caption": caption or "", "parse_mode": parse_mode},
                            files={"video": (file_path.name, f.read())},
                        )

                data = response.json()
                if not response.is_success or not data.get("ok"):
                    error_desc = data.get("description", response.text)
                    error_code = data.get("error_code", response.status_code)
                    raise TelegramAPIError(f"Telegram API error: {error_desc}", response.status_code, error_code)

                result = data.get("result", {})
                message_id = str(result.get("message_id", ""))
                return {"dry_run": False, "provider": "telegram", "chat_id": chat_id_str, "message_id": message_id, "ok": True}
        except httpx.RequestError as exc:
            raise TelegramAPIError(f"Network error: {str(exc)}")

    def set_webhook(self, webhook_url: str) -> dict[str, Any]:
        """
        Configures Telegram to deliver incoming messages to our webhook endpoint.
        """
        if not self.bot_token:
            raise TelegramAPIError("TELEGRAM_BOT_TOKEN is not configured.")

        endpoint = f"{self.base_url}/setWebhook"
        with httpx.Client(timeout=10.0) as client:
            response = client.post(endpoint, json={"url": webhook_url})
            return response.json()
