# -*- coding: utf-8 -*-
"""Recovery codes, encrypted at rest so the owner can view them again.

Held encrypted rather than hashed because the account owner can re-view the
unspent codes -- as GitHub and Google allow -- which a one-way hash forbids.
``verify_token`` decrypts the unspent codes and compares, spending the match;
the login wizard's backup step calls the same method, so it needs no change.
"""

import base64
import secrets

from django.conf import settings
from django.db import models

from django_otp.models import Device, ThrottlingMixin, TimestampMixin

from onadata.libs.utils.field_encryption import decrypt, encrypt

#: How many codes a set holds.
RECOVERY_CODE_COUNT = 10

#: 112 bits, which base32 renders as 23 characters.
RECOVERY_CODE_BYTES = 14


def generate_recovery_code() -> str:
    """A single recovery code: lowercase base32, 112 bits of entropy."""
    return (
        base64.b32encode(secrets.token_bytes(RECOVERY_CODE_BYTES))
        .decode()
        .rstrip("=")
        .lower()
    )


def _normalize(code: str) -> str:
    return code.strip().lower()


class EncryptedRecoveryDevice(TimestampMixin, ThrottlingMixin, Device):
    """A user's recovery-code set, each code stored encrypted."""

    def get_throttle_factor(self):
        return getattr(settings, "OTP_STATIC_THROTTLE_FACTOR", 1)

    @property
    def remaining(self) -> int:
        return self.codes.filter(used=False).count()

    def unspent_codes(self) -> list:
        """The remaining codes in the clear, for re-display to the owner."""
        return [decrypt(code.encrypted_code) for code in self.codes.filter(used=False)]

    def verify_token(self, token):
        verify_allowed, _ = self.verify_is_allowed()
        if not verify_allowed:
            return False
        target = _normalize(token)
        for code in self.codes.filter(used=False):
            if _normalize(decrypt(code.encrypted_code)) == target:
                code.used = True
                code.save(update_fields=["used"])
                self.throttle_reset(commit=False)
                self.set_last_used_timestamp(commit=False)
                self.save()
                return True
        self.throttle_increment()
        return False


class EncryptedRecoveryCode(models.Model):
    """One recovery code, stored encrypted, marked once it is spent."""

    device = models.ForeignKey(
        EncryptedRecoveryDevice, related_name="codes", on_delete=models.CASCADE
    )
    encrypted_code = models.TextField()
    used = models.BooleanField(default=False, db_index=True)
