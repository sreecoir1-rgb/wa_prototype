"""
Unit tests for the TelegramUserClient service (MTProto user account).
Verifies dry-run simulation, session checks, and error handling.
"""
import pytest
from pathlib import Path
from app.services.telegram_user_client import TelegramUserClient, TelegramUserAPIError


def test_telegram_user_client_dry_run():
    """Verifies that dry-run mode returns simulated payloads without hitting the network."""
    client = TelegramUserClient(
        api_id=1234567,
        api_hash="fake_hash_string_32chars123456",
        session_name="test_session",
        dry_run=True,
    )

    res = client.send_message(
        to_phone="+919876543210",
        text="Hello from personal number!",
        media_path=None,
    )

    assert res["dry_run"] is True
    assert res["provider"] == "telegram_user"
    assert res["recipient"] == "+919876543210"
    assert res["ok"] is True
    assert "simulated" in res["message_id"]


def test_telegram_user_client_missing_credentials():
    """Verifies that missing API ID/Hash raises TelegramUserAPIError."""
    client = TelegramUserClient(
        api_id=0,
        api_hash="",
        session_name="test_session",
        dry_run=False,
    )

    with pytest.raises(TelegramUserAPIError) as exc_info:
        client.send_message(to_phone="+919876543210", text="Test")

    assert "TELEGRAM_API_ID and TELEGRAM_API_HASH are not set" in str(exc_info.value)


def test_telegram_user_client_missing_session():
    """Verifies that attempting real send without an authenticated session raises helpful error."""
    dummy_session = "nonexistent_test_session_xyz"
    session_file = Path(__file__).resolve().parent.parent / f"{dummy_session}.session"
    if session_file.exists():
        session_file.unlink()

    client = TelegramUserClient(
        api_id=9999999,
        api_hash="abcdef1234567890abcdef1234567890",
        session_name=dummy_session,
        dry_run=False,
    )

    try:
        with pytest.raises(TelegramUserAPIError) as exc_info:
            client.send_message(to_phone="+919876543210", text="Test")

        assert "Personal Telegram session not found" in str(exc_info.value)
    finally:
        if session_file.exists():
            session_file.unlink()
