# -*- coding: utf-8 -*-
"""Recovery codes, encrypted at rest so the owner can view them again.

Held encrypted rather than hashed because the account owner can re-view the
unspent codes -- as GitHub and Google allow -- which a one-way hash forbids.
``verify_token`` decrypts the unspent codes and compares, spending the match;
the login wizard's backup step calls the same method, so it needs no change.
"""

import base64
import hmac
import logging
import secrets

from django.conf import settings
from django.db import models, transaction
from django.views.decorators.debug import sensitive_variables

from django_otp.models import Device, ThrottlingMixin, TimestampMixin

from onadata.libs.utils.field_encryption import FieldEncryptionError, decrypt

logger = logging.getLogger(__name__)

#: How many codes a set holds.
RECOVERY_CODE_COUNT = 10

#: 112 bits, which base32 renders as 23 characters.
RECOVERY_CODE_BYTES = 14


@sensitive_variables()
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

    class Meta:
        # A DB backstop for the application-level user-row lock: at most one
        # recovery set per user. Partial for symmetry with the authenticator
        # device; recovery sets are always created confirmed.
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                condition=models.Q(confirmed=True),
                name="uniq_confirmed_recovery_device_per_user",
            )
        ]

    def get_throttle_factor(self):
        return getattr(settings, "OTP_STATIC_THROTTLE_FACTOR", 1)

    @property
    def remaining(self) -> int:
        return self.codes.filter(used=False).count()

    @sensitive_variables()
    def unspent_codes(self) -> list[str]:
        """The remaining codes in the clear, for re-display to the owner."""
        return [decrypt(code.encrypted_code) for code in self.codes.filter(used=False)]

    @sensitive_variables()
    def verify_token(self, token):
        target = _normalize(token)
        # Lock the device row and its unspent codes for the whole
        # check-then-spend, and do every check and write on the locked row. The
        # login wizard calls this without the row lock the viewset path holds,
        # so two concurrent submissions could otherwise both read one code as
        # unused and spend it twice, and both read a pre-lock failure count of
        # zero and slip past a backoff that has already tripped. The throttle
        # increment runs on the locked row inside the transaction, as the
        # authenticator device does, so concurrent failures cannot lose it.
        with transaction.atomic():
            locked = type(self).objects.select_for_update().get(pk=self.pk)
            verify_allowed, _ = locked.verify_is_allowed()
            if not verify_allowed:
                return False
            for code in locked.codes.select_for_update().filter(used=False):
                try:
                    stored = _normalize(decrypt(code.encrypted_code)).encode()
                except FieldEncryptionError:
                    logger.error(
                        "Cannot decrypt a recovery code; check "
                        "TWO_FACTOR_FIELD_ENCRYPTION_KEYS."
                    )
                    return False
                if hmac.compare_digest(stored, target.encode()):
                    code.used = True
                    code.save(update_fields=["used"])
                    locked.throttle_reset(commit=False)
                    locked.set_last_used_timestamp(commit=False)
                    locked.save()
                    return True
            locked.throttle_increment(commit=True)
        return False


class EncryptedRecoveryCode(models.Model):
    """One recovery code, stored encrypted, marked once it is spent."""

    device = models.ForeignKey(
        EncryptedRecoveryDevice, related_name="codes", on_delete=models.CASCADE
    )
    encrypted_code = models.TextField()
    used = models.BooleanField(default=False, db_index=True)
