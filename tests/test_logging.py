"""
Tests for structured logging and sensitive data masking filters.
"""
import logging
from app.logging_config import SensitiveDataFilter


def test_sensitive_data_filter_masks_phone_numbers() -> None:
    """Verifies that phone numbers in log messages are replaced with masked variants."""
    filter_instance = SensitiveDataFilter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Sent message to customer +919876543210 successfully.",
        args=(),
        exc_info=None,
    )

    filter_instance.filter(record)
    assert "+91******3210" in record.msg
    assert "9876543210" not in record.msg


def test_sensitive_data_filter_masks_bearer_tokens() -> None:
    """Verifies that Bearer authorization tokens are masked in log messages."""
    filter_instance = SensitiveDataFilter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Sending request with Authorization: Bearer EAAG12345abcdef67890",
        args=(),
        exc_info=None,
    )

    filter_instance.filter(record)
    assert "[HIDDEN_TOKEN]" in record.msg
    assert "EAAG12345abcdef67890" not in record.msg
