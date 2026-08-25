import hmac
from hashlib import sha256


def normalized_email(value: str) -> str:
    return value.strip().lower()


def validate_recipient_email(value: str) -> str:
    email = normalized_email(value)
    local, separator, domain = email.rpartition("@")
    if (
        not separator
        or not local
        or not domain
        or "." not in domain
        or len(email) > 320
        or any(character.isspace() for character in email)
    ):
        raise ValueError("invalid_recipient_email")
    return email


def recipient_email_hmac(email: str, secret: str) -> str:
    normalized = normalized_email(email)
    return hmac.new(secret.encode(), f"BETA-INVITE:{normalized}".encode(), sha256).hexdigest()
