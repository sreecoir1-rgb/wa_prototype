"""
Structured logging configuration with automated privacy masking for PII and secrets.
Ensures that phone numbers and tokens are never logged in plain text.
"""
import logging
import re
from app.services.whatsapp_client import mask_phone_number

# Regex patterns to detect sensitive data in log strings
BEARER_TOKEN_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(\+?[1-9]\d{9,14})")


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter that sanitizes log records before they are output.
    Masks customer phone numbers (e.g. +91******3210) and hides Bearer tokens.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            # 1. Mask Bearer authorization tokens
            sanitized = BEARER_TOKEN_PATTERN.sub(r"\1[HIDDEN_TOKEN]", record.msg)

            # 2. Mask phone numbers
            def replace_phone(match: re.Match) -> str:
                return mask_phone_number(match.group(1))

            sanitized = PHONE_PATTERN.sub(replace_phone, sanitized)
            record.msg = sanitized

        return True


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configures application-wide structured logging with formatting and privacy filters.
    """
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Check if a privacy-filtering handler is already attached to prevent duplicates
    has_filter = any(
        isinstance(h, logging.StreamHandler) and any(isinstance(f, SensitiveDataFilter) for f in h.filters)
        for h in root_logger.handlers
    )
    if not has_filter:
        root_logger.addHandler(handler)
