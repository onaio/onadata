# -*- coding: utf-8 -*-
"""A TOTP authenticator whose seed is encrypted at rest.

django-otp's ``TOTPDevice`` keeps the seed as plaintext hex. The seed is a
permanent shared secret -- one read of it mints codes forever -- so this
project holds it encrypted and decrypts only to compute a code. The
verification contract (``verify_token``) and provisioning URL (``config_url``)
match django-otp's, so the login wizard and the enrolment payload treat this
device exactly as they treat the upstream one.
"""

import logging
import time
from base64 import b32encode
from binascii import unhexlify
from urllib.parse import quote, urlencode

from django.conf import settings
from django.db import models, transaction
from django.views.decorators.debug import sensitive_variables

from django_otp.models import Device, ThrottlingMixin, TimestampMixin
from django_otp.oath import TOTP
from django_otp.util import random_hex

from onadata.libs.utils.field_encryption import (
    FieldEncryptionError,
    decrypt,
    encrypt,
)

logger = logging.getLogger(__name__)

#: 160-bit seed, django-otp's default width.
TOTP_KEY_BYTES = 20


class EncryptedTOTPDevice(TimestampMixin, ThrottlingMixin, Device):
    """A time-based authenticator storing its seed encrypted.

    ``step``/``t0``/``digits``/``tolerance`` are fixed at django-otp's defaults
    rather than stored per row: this project mints every device the same way,
    and leaving them off the table keeps the migration small. ``last_t`` and
    ``drift`` do change per verification, so they are columns.
    """

    encrypted_key = models.TextField(editable=False)
    last_t = models.BigIntegerField(default=-1)
    drift = models.SmallIntegerField(default=0)

    step = 30
    t0 = 0
    digits = 6
    tolerance = 1

    class Meta:
        # A DB backstop for the application-level user-row lock: at most one
        # confirmed managed device per user. Partial, so re-enrolment's
        # transient unconfirmed device does not trip it.
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                condition=models.Q(confirmed=True),
                name="uniq_confirmed_totp_device_per_user",
            )
        ]

    @property
    def key(self):
        return decrypt(self.encrypted_key)

    @key.setter
    def key(self, value):
        self.encrypted_key = encrypt(value)

    @property
    def bin_key(self):
        return unhexlify(self.key)

    def save(self, *args, **kwargs):
        if not self.encrypted_key:
            self.key = random_hex(TOTP_KEY_BYTES)
        super().save(*args, **kwargs)

    def get_throttle_factor(self):
        return getattr(settings, "OTP_TOTP_THROTTLE_FACTOR", 1)

    @property
    def config_url(self):
        """otpauth:// URL for an authenticator app -- as django-otp builds it."""
        label = str(self.user.get_username())
        params = {
            "secret": b32encode(self.bin_key),
            "algorithm": "SHA1",
            "digits": self.digits,
            "period": self.step,
        }
        urlencoded = urlencode(params)
        issuer = self._setting_str("OTP_TOTP_ISSUER")
        if issuer:
            issuer = issuer.replace(":", "")
            label = f"{issuer}:{label}"
            urlencoded += f"&issuer={quote(issuer)}"
        image = self._setting_str("OTP_TOTP_IMAGE")
        if image:
            urlencoded += f"&image={quote(image, safe=':/')}"
        return f"otpauth://totp/{quote(label)}?{urlencoded}"

    def _setting_str(self, name):
        value = getattr(settings, name, None)
        if callable(value):
            value = value(self)
        return value

    @sensitive_variables()
    def verify_token(self, token):
        otp_sync = getattr(settings, "OTP_TOTP_SYNC", True)
        # Lock and re-read the row, and do every check and write on the locked
        # instance. ``last_t`` is the replay guard, and the login wizard
        # verifies without the row lock the viewset path holds, so two
        # concurrent submissions could otherwise read the same stale ``last_t``
        # and both honour one code. The throttle is re-checked here, not on the
        # pre-lock ``self``: a burst would otherwise each read a failure count
        # of zero and slip past a backoff that has already tripped. A failing
        # check must not persist the stale ``last_t`` either -- and
        # ``throttle_increment`` saves the whole row -- so it runs on the locked
        # copy. Reading the locked row also picks up the current ciphertext, so
        # a concurrent key rotation is not clobbered.
        with transaction.atomic():
            locked = type(self).objects.select_for_update().get(pk=self.pk)
            verify_allowed, _ = locked.verify_is_allowed()
            if not verify_allowed:
                return False
            try:
                token = int(token)
            except (ValueError, TypeError):
                verified = False
            else:
                try:
                    key = locked.bin_key
                except FieldEncryptionError:
                    logger.error(
                        "Cannot decrypt an authenticator seed; check "
                        "TWO_FACTOR_FIELD_ENCRYPTION_KEYS."
                    )
                    return False
                totp = TOTP(key, self.step, self.t0, self.digits, locked.drift)
                totp.time = time.time()
                verified = totp.verify(token, self.tolerance, locked.last_t + 1)
            if verified:
                locked.last_t = totp.t()
                if otp_sync:
                    locked.drift = totp.drift
                locked.throttle_reset(commit=False)
                locked.set_last_used_timestamp(commit=False)
                locked.save()
            else:
                locked.throttle_increment(commit=True)
            self.last_t, self.drift = locked.last_t, locked.drift
        return verified
