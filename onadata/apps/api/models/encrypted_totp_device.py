# -*- coding: utf-8 -*-
"""A TOTP authenticator whose seed is encrypted at rest.

django-otp's ``TOTPDevice`` keeps the seed as plaintext hex. The seed is a
permanent shared secret -- one read of it mints codes forever -- so this
project holds it encrypted and decrypts only to compute a code. The
verification contract (``verify_token``) and provisioning URL (``config_url``)
match django-otp's, so the login wizard and the enrolment payload treat this
device exactly as they treat the upstream one.
"""

import time
from base64 import b32encode
from binascii import unhexlify
from urllib.parse import quote, urlencode

from django.conf import settings
from django.db import models

from django_otp.models import Device, ThrottlingMixin, TimestampMixin
from django_otp.oath import TOTP
from django_otp.util import random_hex

from onadata.libs.utils.field_encryption import decrypt, encrypt

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

    def verify_token(self, token):
        otp_sync = getattr(settings, "OTP_TOTP_SYNC", True)
        verify_allowed, _ = self.verify_is_allowed()
        if not verify_allowed:
            return False
        try:
            token = int(token)
        except (ValueError, TypeError):
            verified = False
        else:
            totp = TOTP(self.bin_key, self.step, self.t0, self.digits, self.drift)
            totp.time = time.time()
            verified = totp.verify(token, self.tolerance, self.last_t + 1)
            if verified:
                self.last_t = totp.t()
                if otp_sync:
                    self.drift = totp.drift
                self.throttle_reset(commit=False)
                self.set_last_used_timestamp(commit=False)
                self.save()
        if not verified:
            self.throttle_increment(commit=True)
        return verified
