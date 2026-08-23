from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CredentialVaultError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EncryptedCredential:
    ciphertext: str
    nonce: str
    key_id: str


class CredentialVault:
    def __init__(self, keys: dict[str, str], active_key_id: str) -> None:
        self._keys: dict[str, bytes] = {}
        for key_id, encoded in keys.items():
            try:
                raw = base64.urlsafe_b64decode(encoded.encode())
            except Exception as error:
                raise CredentialVaultError("invalid_provider_credential_key") from error
            if len(raw) != 32:
                raise CredentialVaultError("provider_credential_key_must_be_32_bytes")
            self._keys[key_id] = raw
        self._active_key_id = active_key_id

    @property
    def available(self) -> bool:
        return bool(self._active_key_id and self._active_key_id in self._keys)

    def encrypt(self, payload: dict[str, str], *, aad: str) -> EncryptedCredential:
        if not self.available:
            raise CredentialVaultError("provider_credential_vault_unavailable")
        nonce = os.urandom(12)
        plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ciphertext = AESGCM(self._keys[self._active_key_id]).encrypt(nonce, plaintext, aad.encode())
        return EncryptedCredential(
            ciphertext=base64.urlsafe_b64encode(ciphertext).decode(),
            nonce=base64.urlsafe_b64encode(nonce).decode(),
            key_id=self._active_key_id,
        )

    def decrypt(self, ciphertext: str, nonce: str, key_id: str, *, aad: str) -> dict[str, str]:
        key = self._keys.get(key_id)
        if key is None:
            raise CredentialVaultError("provider_credential_key_unavailable")
        try:
            plaintext = AESGCM(key).decrypt(
                base64.urlsafe_b64decode(nonce),
                base64.urlsafe_b64decode(ciphertext),
                aad.encode(),
            )
            payload = json.loads(plaintext)
        except Exception as error:
            raise CredentialVaultError("provider_credential_decryption_failed") from error
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in payload.items()
        ):
            raise CredentialVaultError("provider_credential_payload_invalid")
        return payload


def generate_key() -> str:
    return base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode()
