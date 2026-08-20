import hmac
from hashlib import sha256
from secrets import choice
from typing import Literal

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_CHARACTERS = 26
CodeDomain = Literal["INV", "ACT"]


def generate_code(domain: CodeDomain) -> str:
    body = "".join(choice(CODE_ALPHABET) for _ in range(CODE_CHARACTERS))
    groups = "-".join(body[index : index + 4] for index in range(0, len(body), 4))
    return f"{domain}-{groups}"


def canonicalize_code(value: str, domain: CodeDomain) -> str:
    compact = "".join(character for character in value.upper().strip() if character.isalnum())
    if not compact.startswith(domain) or len(compact) != len(domain) + CODE_CHARACTERS:
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
