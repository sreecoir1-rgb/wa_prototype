"""
Tests for WhatsAppClient, masking functions, and template payload generation.
"""
import pytest
from app.services.whatsapp_client import WhatsAppClient, mask_phone_number, WhatsAppAPIError


def test_mask_phone_number() -> None:
    """Ensure phone numbers are properly masked for privacy."""
    assert mask_phone_number("+919876543210") == "+91******3210"
    assert mask_phone_number("+12025550199") == "+12*****0199"
    assert mask_phone_number("123") == "****"


def test_build_template_payload() -> None:
    """Verify that the generated JSON body matches Meta Cloud API requirements."""
    client = WhatsAppClient(dry_run=True)
    payload = client.build_template_payload(
        to_phone="+919876543210",
        template_name="hello_world",
        language_code="en_US",
    )

    assert payload["messaging_product"] == "whatsapp"
    assert payload["recipient_type"] == "individual"
    assert payload["to"] == "919876543210"
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "hello_world"
    assert payload["template"]["language"]["code"] == "en_US"


def test_dry_run_simulation_returns_success() -> None:
    """Verify DRY_RUN mode simulates a successful send without touching network."""
    client = WhatsAppClient(
        token="dummy_token_12345",
        phone_number_id="dummy_phone_id",
        dry_run=True,
    )
    result = client.send_template(to_phone="+919876543210")

    assert result["dry_run"] is True
    assert result["messaging_product"] == "whatsapp"
    assert len(result["messages"]) == 1
    assert result["messages"][0]["id"] == "simulated_wamid_dry_run"


def test_live_send_rejects_placeholder_credentials() -> None:
    """Ensure live mode guards against running with placeholder/missing secrets."""
    client = WhatsAppClient(
        token="your_test_token_here",
        phone_number_id="your_phone_number_id_here",
        dry_run=False,
    )
    with pytest.raises(ValueError, match="WHATSAPP_TOKEN is missing or has a placeholder value"):
        client.send_template(to_phone="+919876543210")
