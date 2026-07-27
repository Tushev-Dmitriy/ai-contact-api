"""Helpers for minimizing personal data exposure."""

import hashlib
import hmac


def hash_ip(ip_address: str | None, *, salt: str) -> str | None:
    """Return a stable keyed digest without retaining the source IP."""
    if not ip_address:
        return None
    return hmac.new(
        salt.encode(),
        ip_address.encode(),
        hashlib.sha256,
    ).hexdigest()


def mask_email(email: str) -> str:
    """Mask an email address for diagnostic output."""
    local, separator, domain = email.partition("@")
    if not separator:
        return "***"
    visible = local[:1]
    return f"{visible}***@{domain}"


def mask_phone(phone: str) -> str:
    """Expose only the last two digits of a phone number."""
    digits = "".join(character for character in phone if character.isdigit())
    return f"***{digits[-2:]}" if digits else "***"
