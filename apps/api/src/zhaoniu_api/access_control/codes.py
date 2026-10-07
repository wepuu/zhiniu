import hmac
from hashlib import sha256
from secrets import choice
from typing import Literal

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
INVITATION_CODE_CHARACTERS = 8
LEGACY_INVITATION_CODE_CHARACTERS = 26
ACTIVATION_CODE_CHARACTERS = 26
CodeDomain = Literal["INV", "ACT"]


def generate_code(domain: CodeDomain) -> str:
    length = (
        INVITATION_CODE_CHARACTERS if domain == "INV" else ACTIVATION_CODE_CHARACTERS
    )
    body = "".join(choice(CODE_ALPHABET) for _ in range(length))
    groups = "-".join(body[index : index + 4] for index in range(0, len(body), 4))
    return groups if domain == "INV" else f"{domain}-{groups}"


def canonicalize_code(value: str, domain: CodeDomain) -> str:
    compact = "".join(character for character in value.upper().strip() if character.isalnum())
    if domain == "INV":
        prefixed_lengths = {
            len(domain) + INVITATION_CODE_CHARACTERS,
            len(domain) + LEGACY_INVITATION_CODE_CHARACTERS,
        }
        body = (
            compact[len(domain) :]
            if compact.startswith(domain) and len(compact) in prefixed_lengths
            else compact
        )
        if len(body) not in {
            INVITATION_CODE_CHARACTERS,
            LEGACY_INVITATION_CODE_CHARACTERS,
        }:
            raise ValueError("invalid_code_format")
    else:
        if (
            not compact.startswith(domain)
            or len(compact) != len(domain) + ACTIVATION_CODE_CHARACTERS
        ):
            raise ValueError("invalid_code_format")
        body = compact[len(domain) :]
    if any(character not in CODE_ALPHABET for character in body):
        raise ValueError("invalid_code_format")
    return f"{domain}{body}"


def code_hmac(value: str, domain: CodeDomain, secret: str) -> str:
    canonical = canonicalize_code(value, domain)
    return hmac.new(secret.encode(), f"{domain}:{canonical}".encode(), sha256).hexdigest()


def code_prefix(value: str) -> str:
    return value[:13]
