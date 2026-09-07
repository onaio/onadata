# -*- coding: utf-8 -*-
"""Tests for the recovery-code step of the login wizard."""

from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse

from cryptography.fernet import Fernet
from django_otp.oath import totp
from formtools.wizard.views import normalize_name

from onadata.apps.api.models.encrypted_recovery_device import (
    EncryptedRecoveryCode,
    EncryptedRecoveryDevice,
)
from onadata.apps.api.models.encrypted_totp_device import EncryptedTOTPDevice
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.two_factor_views import LockoutLoginView
from onadata.libs.utils.field_encryption import encrypt

STEP_FIELD = f"{normalize_name(LockoutLoginView.__name__)}-current_step"

RECOVERY_CODE = "abcd2345"

TEST_KEY = Fernet.generate_key().decode()


@override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[TEST_KEY])
class RecoveryCodeStepTestCase(TestBase):
    """The wizard's recovery-code step accepts and explains recovery codes.

    Codes are generated lowercase and the device case-folds on verify, so a code
    typed in caps -- what a phone keyboard offers -- still verifies. These pin
    the wizard to the same case-folding the API does.
    """

    def setUp(self):
        super().setUp()
        # The lockout counter lives in the cache, which the runner does not
        # roll back; clear it so a failed code here does not leak onto the
        # shared user in the next test.
        cache.clear()
        self.addCleanup(cache.clear)
        self.url = reverse("two_factor:login")
        self.client = Client()
        EncryptedTOTPDevice.objects.create(
            user=self.user, name="default", confirmed=True
        )
        device = EncryptedRecoveryDevice.objects.create(
            user=self.user, name="backup", confirmed=True
        )
        EncryptedRecoveryCode.objects.create(
            device=device, encrypted_code=encrypt(RECOVERY_CODE)
        )

    def submit_credentials(self):
        return self.client.post(
            self.url,
            {
                STEP_FIELD: "auth",
                "auth-username": self.user.username,
                "auth-password": self.login_password,
            },
        )

    def submit_recovery_code(self, code):
        return self.client.post(
            self.url, {STEP_FIELD: "backup", "backup-otp_token": code}
        )

    def test_totp_code_completes_login_through_the_token_step(self):
        """The encrypted authenticator verifies through the wizard's own token
        step. The feature rests on the wizard reaching EncryptedTOTPDevice, but
        the other wizard tests enrol a plaintext django-otp device, so this is
        the one that proves the encrypted seed is decrypted and matched here.
        """
        device = EncryptedTOTPDevice.objects.get(user=self.user, name="default")
        token = f"{totp(device.bin_key, device.step, device.t0):06d}"

        self.submit_credentials()
        self.client.post(self.url, {STEP_FIELD: "token", "token-otp_token": token})

        self.assertIn("_auth_user_id", self.client.session)

    def test_a_successful_login_clears_the_failure_alert_counter(self):
        """A run of failures left standing when the user then proves a factor
        would alert the owner on a burst already resolved. The API verify path
        clears the counter on success; the wizard must match.
        """
        from onadata.libs.utils.cache_tools import safe_cache_add
        from onadata.libs.utils.two_factor import _failure_key

        # A prior run of failed attempts left the owner-alert counter standing.
        safe_cache_add(_failure_key(self.user), 3, 1800)
        self.assertIsNotNone(cache.get(_failure_key(self.user)))

        device = EncryptedTOTPDevice.objects.get(user=self.user, name="default")
        token = f"{totp(device.bin_key, device.step, device.t0):06d}"
        self.submit_credentials()
        self.client.post(self.url, {STEP_FIELD: "token", "token-otp_token": token})

        self.assertIn("_auth_user_id", self.client.session)
        self.assertIsNone(cache.get(_failure_key(self.user)))

    def test_backup_action_is_reachable_from_the_token_page(self):
        """The full path a user without their phone takes: after credentials the
        token page must OFFER the recovery step, then a code logs in.

        Upstream counts ``backup_tokens`` from ``staticdevice_set`` alone, which
        this project does not populate, so without ``get_context_data`` the
        template hides "Use Backup Token" and the step is unreachable. The other
        cases here post ``backup`` directly and would pass even then.
        """
        token_page = self.submit_credentials()
        self.assertContains(token_page, "Use Backup Token")

        self.submit_recovery_code(RECOVERY_CODE)
        self.assertIn("_auth_user_id", self.client.session)

    def test_lowercase_recovery_code_completes_login(self):
        """The stored form of the code works -- the control for the case test."""
        self.submit_credentials()
        self.submit_recovery_code(RECOVERY_CODE)
        self.assertIn("_auth_user_id", self.client.session)

    def test_uppercase_recovery_code_completes_login(self):
        """A code typed in caps is accepted, as it is on the API."""
        self.submit_credentials()
        self.submit_recovery_code(RECOVERY_CODE.upper())
        self.assertIn("_auth_user_id", self.client.session)

    def test_invalid_code_message_names_recovery_codes(self):
        """The failure names recovery codes and their single use."""
        self.submit_credentials()
        response = self.submit_recovery_code("zzzz9999")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "recovery code")
        self.assertContains(response, "already been used")
        self.assertNotContains(response, "Invalid token")
