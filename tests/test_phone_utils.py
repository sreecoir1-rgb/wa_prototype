"""
Tests for E.164 phone number normalization.
"""
import pytest
from app.services.phone_utils import normalize_phone_number


def test_normalize_valid_e164_already_formatted() -> None:
    """Verifies already formatted E.164 numbers are untouched."""
    assert normalize_phone_number("+919876543210") == "+919876543210"
    assert normalize_phone_number("+12025550199") == "+12025550199"


def test_normalize_spaces_dashes_parentheses() -> None:
    """Verifies punctuation, spaces, and formatting characters are stripped."""
    assert normalize_phone_number("+91 98765-43210") == "+919876543210"
    assert normalize_phone_number("+1 (202) 555-0199") == "+12025550199"


def test_normalize_local_10_digits() -> None:
    """Verifies 10-digit national numbers receive the default country code (+91)."""
    assert normalize_phone_number("9876543210") == "+919876543210"


def test_normalize_leading_zero() -> None:
    """Verifies domestic numbers with a leading zero are properly handled."""
    assert normalize_phone_number("09876543210") == "+919876543210"


def test_normalize_number_with_country_code_without_plus() -> None:
    """Verifies numbers with country code digits but missing '+' get '+' prefixed."""
    assert normalize_phone_number("919876543210") == "+919876543210"


def test_normalize_custom_country_code() -> None:
    """Verifies custom default country code can be passed."""
    assert normalize_phone_number("2025550199", default_country_code="+1") == "+12025550199"


def test_normalize_rejects_empty_or_whitespace() -> None:
    """Verifies empty or whitespace inputs raise ValueError."""
    with pytest.raises(ValueError, match="must be a non-empty string"):
        normalize_phone_number("")
    with pytest.raises(ValueError, match="must be a non-empty string"):
        normalize_phone_number("   ")


def test_normalize_rejects_alphabetic_characters() -> None:
    """Verifies inputs without digits raise ValueError."""
    with pytest.raises(ValueError, match="contains no digits"):
        normalize_phone_number("abcdef")


def test_normalize_rejects_too_short() -> None:
    """Verifies numbers that are too short to be valid phone numbers are rejected."""
    with pytest.raises(ValueError, match="conform to E.164 standard"):
        normalize_phone_number("12345")
