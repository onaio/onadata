# -*- coding: utf-8 -*-
"""Show-once recovery codes, stored as keyed hashes.

A project-owned django-otp device so the code the user types is never held in
the database: only an HMAC of it is, verified through the same
``verify_token`` contract the login wizard's backup step and the API path both
call.
"""

import base64
import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models

from django_otp.models import Device, ThrottlingMixin, TimestampMixin

#: How many codes a set holds.
RECOVERY_CODE_COUNT = 10

#: 112 bits, which base32 renders as 23 characters -- the entropy at which ASVS
#: 6.5.2 permits a plain keyed hash rather than a slow password hash.
RECOVERY_CODE_BYTES = 14


def _recovery_pepper() -> bytes:
    """The key the stored hashes are computed under.

    A dedicated secret rather than ``SECRET_KEY``: it is what a database reader
    lacks, and rotating it invalidates every printed code, which must not be
    coupled to session-key rotation. Falls back to ``SECRET_KEY`` only so a
    deployment that has not set one is hashed rather than plaintext.
    """
    pepper = getattr(settings, "TWO_FACTOR_RECOVERY_PEPPER", "") or settings.SECRET_KEY
    return pepper.encode()


def hash_recovery_code(raw: str) -> str:
    """Keyed hash of a recovery code, for storage and lookup.

    Deterministic so verification is one indexed lookup, not a scan of ten slow
    hashes; the pepper is what stops the 112-bit code being brute-forced
    offline from the stored hash. Case folded to match how the codes are shown.
    """
    message = raw.strip().lower().encode()
    return hmac.new(_recovery_pepper(), message, hashlib.sha256).hexdigest()


def generate_recovery_code() -> str:
    """A single recovery code: lowercase base32, 112 bits of entropy."""
    return (
        base64.b32encode(secrets.token_bytes(RECOVERY_CODE_BYTES))
        .decode()
        .rstrip("=")
        .lower()
    )


class HashedRecoveryDevice(TimestampMixin, ThrottlingMixin, Device):
    """A user's recovery-code set, held only as keyed hashes.

    Shown once at generation and never re-displayed. ``verify_token`` takes the
    raw code, hashes it, and matches a stored hash, so django-two-factor-auth's
    backup step -- which calls ``device.verify_token(raw)`` -- needs no change.
    """

    def get_throttle_factor(self):
        # ThrottlingMixin leaves this abstract; reuse the static-token factor,
        # since recovery codes throttle the same way django-otp's own do.
        return getattr(settings, "OTP_STATIC_THROTTLE_FACTOR", 1)

    def verify_token(self, token):
        verify_allowed, _ = self.verify_is_allowed()
        if not verify_allowed:
            return False
        match = self.codes.filter(code_hash=hash_recovery_code(token)).first()
        if match is None:
            self.throttle_increment()
            return False
        match.delete()
        self.throttle_reset(commit=False)
        self.set_last_used_timestamp(commit=False)
        self.save()
        return True


class HashedRecoveryCode(models.Model):
    """One unspent recovery code, stored only as its keyed hash."""

    device = models.ForeignKey(
        HashedRecoveryDevice, related_name="codes", on_delete=models.CASCADE
    )
    code_hash = models.CharField(max_length=64, db_index=True)
