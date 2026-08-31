"""Encrypted authenticator seed and recovery codes, plus key rotation."""

import importlib
import time

from django.apps import apps as global_apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from cryptography.fernet import Fernet
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

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
class SeedMigrationTestCase(TestCase):
    """The data migration copies a plaintext django-otp seed in encrypted."""

    def test_existing_seed_is_moved_encrypted_and_original_removed(self):
        migration = importlib.import_module(
            "onadata.apps.api.migrations.0011_migrate_totp_seeds"
        )
        user = get_user_model().objects.create(username="erin")
        old = TOTPDevice.objects.create(user=user, name="default", confirmed=True)
        seed_hex, old_pk = old.key, old.pk

        migration.encrypt_existing_seeds(global_apps, None)

        self.assertFalse(TOTPDevice.objects.filter(pk=old_pk).exists())
        moved = EncryptedTOTPDevice.objects.get(user=user, name="default")
        self.assertTrue(moved.confirmed)
        self.assertEqual(moved.key, seed_hex)
        self.assertNotIn(seed_hex, moved.encrypted_key)
