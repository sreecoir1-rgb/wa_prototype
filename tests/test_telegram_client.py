"""
Unit tests for the TelegramClient service.
Verifies dry-run simulation, real request payload building, and error handling.
"""
import pytest
import httpx
from app.services.telegram_client import TelegramClient, TelegramAPIError, mask_chat_id


def test_mask_chat_id():
    """Verifies privacy masking for Telegram chat IDs."""
    assert mask_chat_id("123456789") == "12****89"
    assert mask_chat_id("123") == "****"


def test_telegram_client_dry_run():
    """Verifies dry-run mode returns simulated responses without making network requests."""
    client = TelegramClient(bot_token="test_fake_token", dry_run=True)
    result = client.send_message(chat_id="987654321", text="Test message")

    assert result["dry_run"] is True
    assert result["provider"] == "telegram"
    assert result["chat_id"] == "987654321"
    assert result["message_id"] == "simulated_tg_wamid"
    assert result["ok"] is True


def test_telegram_client_real_send_mock(monkeypatch):
    """Verifies real send execution calls the Telegram endpoint and parses result."""
    client = TelegramClient(bot_token="test_fake_token", dry_run=False)

    fake_response = httpx.Response(
        200,
        json={
            "ok": True,
            "result": {
                "message_id": 999,
                "chat": {"id": 12345, "type": "private"},
                "text": "Hello Telegram",
            },
        },
        request=httpx.Request("POST", "https://api.telegram.org"),
    )

    def mock_post(*args, **kwargs):
        return fake_response

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    result = client.send_message(chat_id="12345", text="Hello Telegram")
    assert result["dry_run"] is False
    assert result["message_id"] == "999"
    assert result["ok"] is True


def test_telegram_client_api_error_handling(monkeypatch):
    """Verifies that API errors from Telegram raise TelegramAPIError with details."""
    client = TelegramClient(bot_token="test_fake_token", dry_run=False)

    error_response = httpx.Response(
        403,
        json={
            "ok": False,
            "error_code": 403,
            "description": "Forbidden: bot was blocked by the user",
        },
        request=httpx.Request("POST", "https://api.telegram.org"),
    )

    def mock_post(*args, **kwargs):
        return error_response

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    with pytest.raises(TelegramAPIError) as exc_info:
        client.send_message(chat_id="12345", text="Hello")

    assert exc_info.value.status_code == 403
    assert "bot was blocked by the user" in str(exc_info.value)
