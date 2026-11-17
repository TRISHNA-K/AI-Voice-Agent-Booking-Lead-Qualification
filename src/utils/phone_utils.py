"""Phone number sanitization and E.164 normalization utilities."""

import re
from typing import Optional


def normalize_phone_number(raw_phone: str, default_country_code: str = "+1") -> str:
    """
    Sanitize and normalize a phone string into E.164 format.
    
    Examples:
    - '(555) 123-4567' -> '+15551234567'
    - '5551234567' -> '+15551234567'
    - '+44 20 7946 0991' -> '+442079460991'
    """
    if not raw_phone:
        return ""

    digits = re.sub(r"[^\d+]", "", raw_phone)
    if digits.startswith("+"):
        return digits

    # If 10 digits (US/Canada format), prefix with +1
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"

    return f"{default_country_code}{digits}" if not digits.startswith("+") else digits


def mask_phone_number(phone: str) -> str:
    """Mask phone number for safe logging (e.g. +1***-***-4567)."""
    normalized = normalize_phone_number(phone)
    if len(normalized) <= 4:
        return "****"
    return f"{normalized[:2]}***-***-{normalized[-4:]}"
