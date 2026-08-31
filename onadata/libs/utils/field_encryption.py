"""Symmetric field encryption for second-factor secrets.

The TOTP seed has to be recovered to recompute codes, and recovery codes are
shown more than once, so both are encrypted at rest rather than hashed. Keys
live in application config, not the database, so a database-only leak cannot
read them. The key list is ordered: the first key encrypts, every key is tried
for decryption, which is what lets a new key be rolled in ahead of the old one
and the stored values re-encrypted without a flag day.
"""

from django.conf import settings

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class FieldEncryptionError(Exception):
    """No usable key is configured, or a value cannot be decrypted."""


def _configured_keys():
    keys = getattr(settings, "TWO_FACTOR_FIELD_ENCRYPTION_KEYS", None) or []
    if not keys:
        raise FieldEncryptionError(
            "TWO_FACTOR_FIELD_ENCRYPTION_KEYS is not configured; second-factor "
            "secrets cannot be encrypted."
        )
    return keys


def _cipher(keys=None):
    keys = keys if keys is not None else _configured_keys()
    if not keys:
        raise FieldEncryptionError("No encryption keys supplied.")
    return MultiFernet([Fernet(key) for key in keys])


def encrypt(value, keys=None):
    if value is None:
        return None
    return _cipher(keys).encrypt(value.encode()).decode()


def decrypt(token, keys=None):
    if token is None:
        return None
    try:
        return _cipher(keys).decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise FieldEncryptionError(
            "Could not decrypt value with any configured key."
        ) from exc


def reencrypt_to_primary(token, keys=None):
    """Return the token re-encrypted under the first key, read with any key."""
    if token is None:
        return None
    try:
        return _cipher(keys).rotate(token.encode()).decode()
    except InvalidToken as exc:
        raise FieldEncryptionError(
            "Could not decrypt value with any configured key."
        ) from exc
