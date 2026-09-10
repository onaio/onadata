"""EncryptedTOTPDevice: seed encryption at rest, verification, uniqueness."""

import time

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from cryptography.fernet import Fernet
from django_otp.oath import TOTP

from onadata.apps.api.models.encrypted_totp_device import EncryptedTOTPDevice
from onadata.libs.utils.field_encryption import decrypt

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()


def _current_token(device) -> int:
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits)
    totp.time = time.time()
    return totp.token()


@override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A])
class EncryptedTOTPDeviceTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(username="bob")

    def test_seed_is_encrypted_at_rest_but_reads_back(self):
        device = EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=True
        )
        self.assertTrue(device.encrypted_key)
        self.assertNotIn(device.key, device.encrypted_key)
        reread = EncryptedTOTPDevice.objects.get(pk=device.pk)
        self.assertEqual(reread.key, device.key)
        self.assertEqual(decrypt(reread.encrypted_key), device.key)

    def test_verify_accepts_current_token_then_rejects_its_replay(self):
        device = EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=True
        )
        token = _current_token(device)
        self.assertTrue(device.verify_token(token))
        self.assertFalse(device.verify_token(token))

    def test_verify_rejects_a_wrong_token(self):
        device = EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=True
        )
        self.assertFalse(device.verify_token(000000))

    def test_config_url_carries_the_secret(self):
        device = EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=True
        )
        self.assertTrue(device.config_url.startswith("otpauth://totp/"))
        self.assertIn("secret=", device.config_url)


@override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A])
class UndecryptableSeedTestCase(TestCase):
    """A seed whose key is no longer configured fails verification closed,
    rather than raising a 500 that would lock every enrolled user out loudly."""

    def setUp(self):
        self.user = get_user_model().objects.create(username="frank")

    def test_totp_verify_fails_closed_when_the_seed_cannot_be_decrypted(self):
        device = EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=True
        )
        token = _current_token(device)
        self.assertEqual(EncryptedTOTPDevice.objects.get(pk=device.pk).key, device.key)
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_B]):
            self.assertFalse(
                EncryptedTOTPDevice.objects.get(pk=device.pk).verify_token(token)
            )


@override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A])
class ManagedDeviceUniquenessTestCase(TestCase):
    """A DB backstop enforces one confirmed managed device per user, without
    tripping on the transient unconfirmed device a re-enrolment creates."""

    def setUp(self):
        self.user = get_user_model().objects.create(username="grace")

    def test_two_confirmed_authenticators_are_refused(self):
        EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=True
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EncryptedTOTPDevice.objects.create(
                    user=self.user, name="default", confirmed=True
                )

    def test_an_unconfirmed_authenticator_is_allowed_beside_a_confirmed_one(self):
        EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=True
        )
        pending = EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=False
        )
        self.assertIsNotNone(pending.pk)
