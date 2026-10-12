"""AES-256-GCM field-level encryption for client PII.

Stored format: "v1:" + base64(nonce[12] + ciphertext + tag[16]).
Run `python -m app.crypto genkey` to generate a key for PII_ENCRYPTION_KEY.
"""

from __future__ import annotations

import base64
import os
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PREFIX = "v1:"


class EncryptionKeyError(RuntimeError):
    pass


def _load_key() -> bytes:
    from app.config import get_settings

    raw = get_settings().pii_encryption_key
    if not raw:
        raise EncryptionKeyError("PII_ENCRYPTION_KEY is not set. Generate one with: python -m app.crypto genkey")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise EncryptionKeyError("PII_ENCRYPTION_KEY must be base64 of exactly 32 bytes (AES-256).")
    return key


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(_load_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    return PREFIX + base64.b64encode(nonce + ct).decode("ascii")


def decrypt(token: str) -> str:
    if not token.startswith(PREFIX):
        raise ValueError("Unrecognised ciphertext format")
    blob = base64.b64decode(token[len(PREFIX) :])
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(_load_key()).decrypt(nonce, ct, None).decode("utf-8")


def generate_key() -> str:
    return base64.b64encode(AESGCM.generate_key(bit_length=256)).decode("ascii")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "genkey":
        print(generate_key())
    else:
        print("usage: python -m app.crypto genkey")
