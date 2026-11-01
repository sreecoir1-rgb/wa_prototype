"""
WhatsApp Business Cloud API client.
Handles sending template messages, dry-run simulation, and response parsing.
"""
import logging
from typing import Any
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class WhatsAppAPIError(Exception):
    """Raised when the Meta WhatsApp Cloud API returns an error response."""
    def __init__(self, message: str, status_code: int | None = None, error_code: int | None = None, details: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


def mask_phone_number(phone: str) -> str:
    """
    Masks a phone number to protect customer privacy in logs.
    Example: '+919876543210' -> '+91******3210'
    """
    if not phone or len(phone) < 7:
        return "****"
    prefix = phone[:3]
    suffix = phone[-4:]
    masked_part = "*" * max(len(phone) - 7, 4)
    return f"{prefix}{masked_part}{suffix}"


class WhatsAppClient:
    """
    Client for interacting with the official Meta WhatsApp Business Cloud API.
    """

    def __init__(
        self,
        token: str | None = None,
        phone_number_id: str | None = None,
        dry_run: bool | None = None,
        api_version: str = "v22.0",
    ):
        self.token = token if token is not None else settings.WHATSAPP_TOKEN
        self.phone_number_id = phone_number_id if phone_number_id is not None else settings.WHATSAPP_PHONE_NUMBER_ID
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN
        self.api_version = api_version

    @property
    def messages_endpoint(self) -> str:
        """Constructs the Meta Graph API endpoint URL for sending messages."""
        return f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"

    def build_template_payload(
        self,
        to_phone: str,
        template_name: str = "hello_world",
        language_code: str = "en_US",
    ) -> dict[str, Any]:
        """
        Builds the standard JSON request body for sending an approved WhatsApp template.
        """
        # Clean leading whitespace and ensure number starts without '+' for Meta's 'to' field if required,
        # but E.164 without '+' or with '+' is accepted by Graph API (digits only is preferred by Meta).
        normalized_to = to_phone.strip().lstrip("+")

        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalized_to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                }
            }
        }

    def send_template(
        self,
        to_phone: str,
        template_name: str = "hello_world",
        language_code: str = "en_US",
    ) -> dict[str, Any]:
        """
        Sends an approved template message to the recipient phone number.
        In DRY_RUN mode, prints the request details and skips sending the actual HTTP request.
        """
        payload = self.build_template_payload(
            to_phone=to_phone,
            template_name=template_name,
            language_code=language_code,
        )
        masked_to = mask_phone_number(to_phone)

        # 1. DRY RUN (Simulation Mode)
        if self.dry_run:
            print("=" * 60)
            print(" [DRY RUN ACTIVE] WhatsApp message send simulation")
            print("=" * 60)
            print(f" Endpoint:  {self.messages_endpoint}")
            print(f" Recipient: {masked_to}")
            print(f" Template:  {template_name} ({language_code})")
            print(" Headers:    Authorization: Bearer [HIDDEN - NEVER LOGGED]")
            print(f" Payload:   {payload}")
            print(" Result:    Simulated success (no real HTTP call was made)")
            print("=" * 60)
            return {
                "dry_run": True,
                "messaging_product": "whatsapp",
                "contacts": [{"input": to_phone, "wa_id": payload["to"]}],
                "messages": [{"id": "simulated_wamid_dry_run"}],
            }

        # 2. REAL SEND MODE
        # Validate that necessary secrets are configured before calling the API
        if not self.token or self.token == "your_test_token_here":
            raise ValueError(
                "WHATSAPP_TOKEN is missing or has a placeholder value in .env. "
                "Please add a valid temporary or permanent access token from Meta."
            )
        if not self.phone_number_id or self.phone_number_id == "your_phone_number_id_here":
            raise ValueError(
                "WHATSAPP_PHONE_NUMBER_ID is missing or has a placeholder value in .env. "
                "Please add your Phone Number ID from the Meta Developer Dashboard."
            )

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    self.messages_endpoint,
                    headers=headers,
                    json=payload,
                )
        except httpx.RequestError as exc:
            raise WhatsAppAPIError(f"Network error while connecting to Meta Graph API: {exc}") from exc

        # Parse success or error responses
        try:
            response_data = response.json()
        except Exception:
            response_data = {"raw": response.text}

        if response.is_success:
            return response_data

        # If we reach here, Meta returned an error status code (4xx or 5xx)
        error_info = response_data.get("error", {}) if isinstance(response_data, dict) else {}
        error_code = error_info.get("code")
        error_message = error_info.get("message", "Unknown error")
        error_subcode = error_info.get("error_subcode")
        fbtrace_id = error_info.get("fbtrace_id", "N/A")

        # Provide beginner-friendly guidance based on Meta's common error codes
        hint = "Check Meta Developer documentation."
        if error_code == 190:
            hint = "Your WhatsApp access token is invalid or expired. Refresh it in the Meta Developer Portal."
        elif error_code == 131030:
            hint = (
                f"Recipient {masked_to} is not in your allowed test numbers. "
                "Go to Meta Dashboard > WhatsApp > API Setup > 'To' dropdown > 'Manage phone number list' to add it."
            )
        elif error_code == 100:
            hint = "Invalid parameter or template name. Verify the phone number format (E.164) and template status."

        formatted_error = (
            f"WhatsApp Cloud API Error ({response.status_code}) [Code {error_code}, Subcode {error_subcode}]: "
            f"{error_message}\nTrace ID: {fbtrace_id}\nHint: {hint}"
        )
        raise WhatsAppAPIError(
            message=formatted_error,
            status_code=response.status_code,
            error_code=error_code,
            details=error_info,
        )
