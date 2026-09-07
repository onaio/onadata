"""Two-factor field-encryption key rotation command and the startup checks."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from cryptography.fernet import Fernet

from onadata.apps.api.checks import (
    two_factor_encryption_keys_check,
    two_factor_secret_key_check,
    two_factor_support_email_check,
)
from onadata.settings.common import INSECURE_DEFAULT_SECRET_KEY
from onadata.apps.api.models.encrypted_recovery_device import (
    EncryptedRecoveryCode,
    EncryptedRecoveryDevice,
    generate_recovery_code,
)
from onadata.apps.api.models.encrypted_totp_device import EncryptedTOTPDevice
from onadata.libs.utils.field_encryption import encrypt

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()


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
            device = EncryptedTOTPDevice.objects.create(
                user=self.user, name="default", confirmed=True
            )
            seed = device.key
        # Old key already dropped: the seed under KEY_A cannot be re-encrypted.
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_B]):
            with self.assertRaises(CommandError):
                call_command("rotate_two_factor_encryption_key")
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A]):
            self.assertEqual(EncryptedTOTPDevice.objects.get(pk=device.pk).key, seed)

    @override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A])
    def test_verify_passes_when_the_keys_decrypt(self):
        EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=True
        )
        out = StringIO()
        call_command("rotate_two_factor_encryption_key", "--verify", stdout=out)
        self.assertIn("decrypt with the configured keys", out.getvalue())

    def test_verify_raises_when_a_secret_cannot_be_decrypted(self):
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A]):
            EncryptedTOTPDevice.objects.create(
                user=self.user, name="default", confirmed=True
            )
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_B]):
            with self.assertRaises(CommandError):
                call_command("rotate_two_factor_encryption_key", "--verify")

    def test_purge_deletes_undecryptable_devices(self):
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A]):
            EncryptedTOTPDevice.objects.create(
                user=self.user, name="default", confirmed=True
            )
            recovery = EncryptedRecoveryDevice.objects.create(
                user=self.user, name="backup", confirmed=True
            )
            EncryptedRecoveryCode.objects.create(
                device=recovery, encrypted_code=encrypt(generate_recovery_code())
            )
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_B]):
            call_command(
                "rotate_two_factor_encryption_key",
                "--purge-undecryptable",
                "--noinput",
                stdout=StringIO(),
            )
        self.assertFalse(EncryptedTOTPDevice.objects.filter(user=self.user).exists())
        self.assertFalse(
            EncryptedRecoveryDevice.objects.filter(user=self.user).exists()
        )
        self.assertEqual(EncryptedRecoveryCode.objects.count(), 0)

    @override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A])
    def test_purge_leaves_decryptable_devices_untouched(self):
        EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=True
        )
        out = StringIO()
        call_command(
            "rotate_two_factor_encryption_key",
            "--purge-undecryptable",
            "--noinput",
            stdout=out,
        )
        self.assertTrue(EncryptedTOTPDevice.objects.filter(user=self.user).exists())
        self.assertIn("nothing to purge", out.getvalue())


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


class TwoFactorSupportEmailCheckTestCase(SimpleTestCase):
    """Two-factor requires SUPPORT_EMAIL, checked at startup."""

    @override_settings(ENABLE_TWO_FACTOR=False, SUPPORT_EMAIL="")
    def test_no_error_when_two_factor_is_off(self):
        self.assertEqual(two_factor_support_email_check(None), [])

    @override_settings(ENABLE_TWO_FACTOR=True, SUPPORT_EMAIL="")
    def test_error_when_on_without_support_email(self):
        errors = two_factor_support_email_check(None)
        self.assertEqual([error.id for error in errors], ["api.E003"])

    @override_settings(ENABLE_TWO_FACTOR=True, SUPPORT_EMAIL="help@example.com")
    def test_no_error_when_support_email_is_set(self):
        self.assertEqual(two_factor_support_email_check(None), [])


class TwoFactorSecretKeyCheckTestCase(SimpleTestCase):
    """Two-factor refuses the shipped default SECRET_KEY, checked at startup."""

    @override_settings(ENABLE_TWO_FACTOR=False, SECRET_KEY=INSECURE_DEFAULT_SECRET_KEY)
    def test_no_error_when_two_factor_is_off(self):
        self.assertEqual(two_factor_secret_key_check(None), [])

    @override_settings(ENABLE_TWO_FACTOR=True, SECRET_KEY=INSECURE_DEFAULT_SECRET_KEY)
    def test_error_when_on_with_the_default_secret_key(self):
        errors = two_factor_secret_key_check(None)
        self.assertEqual([error.id for error in errors], ["api.E004"])

    @override_settings(ENABLE_TWO_FACTOR=True, SECRET_KEY="a-unique-deployment-secret")
    def test_no_error_when_secret_key_is_overridden(self):
        self.assertEqual(two_factor_secret_key_check(None), [])
