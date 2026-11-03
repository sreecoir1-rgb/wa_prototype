"""
Phone number normalization and validation utilities adhering to the E.164 international standard.
"""
import re


def normalize_phone_number(raw_phone: str, default_country_code: str = "+91") -> str:
    """
    Normalizes a phone number into strict E.164 international format (+[country code][number]).

    Examples:
        - "9876543210"        -> "+919876543210" (using default +91)
        - "09876543210"       -> "+919876543210" (strips leading 0)
        - "+91 98765-43210"   -> "+919876543210"
        - "+1 (202) 555-0199" -> "+12025550199"

    Raises:
        ValueError: If the input cannot be parsed into a valid E.164 phone number.
    """
    if not isinstance(raw_phone, str) or not raw_phone.strip():
        raise ValueError("Phone number must be a non-empty string.")

    cleaned = raw_phone.strip()
    if cleaned.lower().startswith(("tg_", "tg:")):
        digits = re.sub(r"\D", "", cleaned)
        if not digits:
            raise ValueError(f"Telegram ID '{raw_phone}' contains no digits.")
        return f"tg_{digits}"

    has_plus = cleaned.startswith("+")

    # Remove all non-digit characters
    digits_only = re.sub(r"\D", "", cleaned)

    if not digits_only:
        raise ValueError(f"Phone number '{raw_phone}' contains no digits.")

    # Strip domestic leading trunk zero if present (e.g. 09876543210 -> 9876543210)
    if not has_plus and digits_only.startswith("0") and len(digits_only) > 10:
        digits_only = digits_only[1:]

    # A phone number (national or international) needs at least 7 digits
    if len(digits_only) < 7:
        raise ValueError(
            f"Invalid phone number '{raw_phone}'. "
            f"Too short ({len(digits_only)} digits) to conform to E.164 standard."
        )

    cc_digits = re.sub(r"\D", "", default_country_code)

    if has_plus:
        candidate = f"+{digits_only}"
    else:
        # If user passed a standard 10-digit number, prepend default country code
        if len(digits_only) == 10:
            candidate = f"+{cc_digits}{digits_only}"
        # If number already starts with the country code digits (e.g. '919876543210')
        elif digits_only.startswith(cc_digits) and len(digits_only) == len(cc_digits) + 10:
            candidate = f"+{digits_only}"
        else:
            candidate = f"+{cc_digits}{digits_only}"

    # E.164 standard:
    # Starts with '+', first digit 1-9, total 7 to 15 digits
    e164_pattern = re.compile(r"^\+[1-9]\d{6,14}$")
    if not e164_pattern.match(candidate):
        raise ValueError(
            f"Invalid phone number '{raw_phone}'. "
            f"Normalized value '{candidate}' does not conform to E.164 standard."
        )

    return candidate
