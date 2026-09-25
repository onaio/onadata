"""EncryptedRecoveryDevice: single-use recovery codes, encrypted at rest."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from cryptography.fernet import Fernet

from onadata.apps.api.models.encrypted_recovery_device import (
    EncryptedRecoveryCode,
    EncryptedRecoveryDevice,
    generate_recovery_code,
)
from onadata.libs.utils.field_encryption import encrypt

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()


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

    def test_a_non_string_token_is_rejected_without_raising(self):
        for bad in (None, 123456):
            self.assertFalse(self.device.verify_token(bad))
        self.assertEqual(self.device.remaining, 3)

    def test_unspent_codes_skips_an_undecryptable_code(self):
        """unspent_codes degrades like verify_token: a code the current keys
        cannot read is skipped, not a 500."""
        device = EncryptedRecoveryDevice.objects.create(
            user=self.user, name="third-backup", confirmed=True
        )
        good = generate_recovery_code()
        EncryptedRecoveryCode.objects.create(
            device=device, encrypted_code=encrypt(good)
        )
        EncryptedRecoveryCode.objects.create(
            device=device,
            encrypted_code=encrypt(generate_recovery_code(), keys=[KEY_B]),
        )

        self.assertEqual(device.unspent_codes(), [good])

    def test_an_undecryptable_code_does_not_block_a_valid_one(self):
        """A code the current keys cannot read (e.g. a key dropped mid
        rotation) is skipped, not fatal: the valid codes still verify."""
        device = EncryptedRecoveryDevice.objects.create(
            user=self.user, name="second-backup", confirmed=True
        )
        # The undecryptable code is created first, so it is iterated (and
        # skipped) before the good one -- the loop must not bail out on it.
        EncryptedRecoveryCode.objects.create(
            device=device,
            encrypted_code=encrypt(generate_recovery_code(), keys=[KEY_B]),
        )
        good = generate_recovery_code()
        EncryptedRecoveryCode.objects.create(
            device=device, encrypted_code=encrypt(good)
        )

        self.assertTrue(device.verify_token(good))


@override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_A])
class UndecryptableRecoveryCodeTestCase(TestCase):
    """A code whose key is no longer configured fails verification closed,
    rather than raising a 500 that would lock every enrolled user out loudly."""

    def setUp(self):
        self.user = get_user_model().objects.create(username="frank")

    def test_recovery_verify_fails_closed_when_a_code_cannot_be_decrypted(self):
        device = EncryptedRecoveryDevice.objects.create(
            user=self.user, name="backup", confirmed=True
        )
        code = generate_recovery_code()
        EncryptedRecoveryCode.objects.create(
            device=device, encrypted_code=encrypt(code)
        )
        self.assertIn(code, device.unspent_codes())
        with override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[KEY_B]):
            self.assertFalse(device.verify_token(code))
