"""Encrypted authenticator seed and recovery codes, plus key rotation."""

import time
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings

from cryptography.fernet import Fernet
from django_otp.oath import TOTP

from onadata.apps.api.checks import two_factor_encryption_keys_check
from onadata.apps.api.models.encrypted_recovery_device import (
    EncryptedRecoveryCode,
    EncryptedRecoveryDevice,
    generate_recovery_code,
)
from onadata.apps.api.models.encrypted_totp_device import EncryptedTOTPDevice
from onadata.libs.utils.field_encryption import decrypt, encrypt

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
class EncryptedRecoveryDeviceTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(username="carol")
        self.device = EncryptedRecoveryDevice.objects.create(
            user=self.user, name="backup", confirmed=True
        )
        self.codes = [generate_recovery_code() for _ in range(3)]
        EncryptedRecoveryCode.objects.bulk_create(
            EncryptedRecoveryCode(device=self.device, encrypted_code=encrypt(code))
            for code in self.codes
        )

    def test_unspent_codes_are_readable_again(self):
        self.assertCountEqual(self.device.unspent_codes(), self.codes)
        self.assertEqual(self.device.remaining, 3)

    def test_verify_spends_one_code_case_insensitively(self):
        self.assertTrue(self.device.verify_token(self.codes[0].upper()))
        self.assertEqual(self.device.remaining, 2)
        self.assertNotIn(self.codes[0], self.device.unspent_codes())

    def test_a_spent_code_does_not_verify_again(self):
        self.assertTrue(self.device.verify_token(self.codes[0]))
        self.assertFalse(self.device.verify_token(self.codes[0]))

    def test_a_code_not_in_the_set_does_not_verify(self):
        self.assertFalse(self.device.verify_token("not-a-real-code"))
        self.assertEqual(self.device.remaining, 3)


class RotateEncryptionKeyTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(username="dave")

    def test_rotation_reencrypts_seeds_and_codes_under_the_new_primary(self):
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A]):
            device = EncryptedTOTPDevice.objects.create(
                user=self.user, name="default", confirmed=True
            )
            seed = device.key
            recovery = EncryptedRecoveryDevice.objects.create(
                user=self.user, name="backup", confirmed=True
            )
            code = generate_recovery_code()
            EncryptedRecoveryCode.objects.create(
                device=recovery, encrypted_code=encrypt(code)
            )

        # New key rolled in ahead of the old, run the rotation.
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_B, KEY_A]):
            call_command("rotate_two_factor_encryption_key")

        # The old key alone can no longer read the values; the new key can.
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_B]):
            self.assertEqual(EncryptedTOTPDevice.objects.get(pk=device.pk).key, seed)
            self.assertEqual(
                EncryptedRecoveryDevice.objects.get(pk=recovery.pk).unspent_codes(),
                [code],
            )

    @override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A])
    def test_dry_run_counts_without_re_encrypting(self):
        device = EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=True
        )
        stored = EncryptedTOTPDevice.objects.get(pk=device.pk).encrypted_key

        out = StringIO()
        call_command("rotate_two_factor_encryption_key", "--dry-run", stdout=out)

        self.assertIn("Would re-encrypt 1 authenticator seed", out.getvalue())
        self.assertEqual(
            EncryptedTOTPDevice.objects.get(pk=device.pk).encrypted_key, stored
        )

    def test_rotation_stops_when_a_secret_cannot_be_decrypted(self):
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A]):
            EncryptedTOTPDevice.objects.create(
                user=self.user, name="default", confirmed=True
            )
        # Old key already dropped: the seed under KEY_A cannot be re-encrypted.
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_B]):
            with self.assertRaises(CommandError):
                call_command("rotate_two_factor_encryption_key")


class TwoFactorEncryptionKeysCheckTestCase(SimpleTestCase):
    """The startup check couples ENABLE_TWO_FACTOR with a usable key."""

    @override_settings(ENABLE_TWO_FACTOR=False, TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[])
    def test_no_error_when_two_factor_is_off(self):
        self.assertEqual(two_factor_encryption_keys_check(None), [])

    @override_settings(ENABLE_TWO_FACTOR=True, TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[])
    def test_error_when_on_without_a_key(self):
        errors = two_factor_encryption_keys_check(None)
        self.assertEqual([error.id for error in errors], ["api.E001"])

    @override_settings(
        ENABLE_TWO_FACTOR=True,
        TWO_FACTOR_FIELD_ENCRYPTION_KEYS=["not-a-valid-fernet-key"],
    )
    def test_error_when_a_key_is_invalid(self):
        errors = two_factor_encryption_keys_check(None)
        self.assertEqual([error.id for error in errors], ["api.E002"])

    @override_settings(ENABLE_TWO_FACTOR=True, TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A])
    def test_no_error_with_a_valid_key(self):
        self.assertEqual(two_factor_encryption_keys_check(None), [])


@override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A])
class UndecryptableSecretTestCase(TestCase):
    """A device whose key is no longer configured fails verification closed,
    rather than raising a 500 that would lock every enrolled user out loudly."""

    def setUp(self):
        self.user = get_user_model().objects.create(username="frank")

    def test_totp_verify_fails_closed_when_the_seed_cannot_be_decrypted(self):
        device = EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=True
        )
        token = _current_token(device)
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_B]):
            self.assertFalse(device.verify_token(token))

    def test_recovery_verify_fails_closed_when_a_code_cannot_be_decrypted(self):
        device = EncryptedRecoveryDevice.objects.create(
            user=self.user, name="backup", confirmed=True
        )
        code = generate_recovery_code()
        EncryptedRecoveryCode.objects.create(
            device=device, encrypted_code=encrypt(code)
        )
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_B]):
            self.assertFalse(device.verify_token(code))


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

    def test_two_recovery_sets_are_refused(self):
        EncryptedRecoveryDevice.objects.create(
            user=self.user, name="backup", confirmed=True
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EncryptedRecoveryDevice.objects.create(
                    user=self.user, name="backup", confirmed=True
                )
