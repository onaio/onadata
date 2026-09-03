from cryptography.fernet import Fernet
from django.test import SimpleTestCase, override_settings

from onadata.libs.utils.field_encryption import (
    FieldEncryptionError,
    decrypt,
    encrypt,
    reencrypt_to_primary,
)

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()


class FieldEncryptionTestCase(SimpleTestCase):
    def test_round_trip(self):
        token = encrypt("s33d-value", keys=[KEY_A])
        self.assertNotEqual(token, "s33d-value")
        self.assertEqual(decrypt(token, keys=[KEY_A]), "s33d-value")

    def test_none_passes_through(self):
        self.assertIsNone(encrypt(None, keys=[KEY_A]))
        self.assertIsNone(decrypt(None, keys=[KEY_A]))

    def test_ciphertext_differs_per_call(self):
        self.assertNotEqual(encrypt("x", keys=[KEY_A]), encrypt("x", keys=[KEY_A]))

    def test_secondary_key_still_decrypts_after_new_primary(self):
        token = encrypt("v", keys=[KEY_A])
        self.assertEqual(decrypt(token, keys=[KEY_B, KEY_A]), "v")

    def test_decrypt_without_the_key_raises(self):
        token = encrypt("v", keys=[KEY_A])
        with self.assertRaises(FieldEncryptionError):
            decrypt(token, keys=[KEY_B])

    def test_reencrypt_moves_value_to_primary_key(self):
        token = encrypt("v", keys=[KEY_A])
        rotated = reencrypt_to_primary(token, keys=[KEY_B, KEY_A])
        self.assertEqual(decrypt(rotated, keys=[KEY_B]), "v")

    @override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[])
    def test_missing_configuration_raises(self):
        with self.assertRaises(FieldEncryptionError):
            encrypt("v")
