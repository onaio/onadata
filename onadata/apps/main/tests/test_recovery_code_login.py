# -*- coding: utf-8 -*-
"""Tests for the recovery-code step of the login wizard."""

from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from django_otp.plugins.otp_totp.models import TOTPDevice
from formtools.wizard.views import normalize_name

from onadata.apps.api.models.hashed_recovery_device import (
    HashedRecoveryCode,
    HashedRecoveryDevice,
    hash_recovery_code,
)
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.two_factor_views import LockoutLoginView

STEP_FIELD = f"{normalize_name(LockoutLoginView.__name__)}-current_step"

RECOVERY_CODE = "abcd2345"


class RecoveryCodeStepTestCase(TestBase):
    """The wizard's recovery-code step accepts and explains recovery codes.

    Codes are generated lowercase and the device hashes case-folded, so a code
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
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        device = HashedRecoveryDevice.objects.create(
            user=self.user, name="backup", confirmed=True
        )
        HashedRecoveryCode.objects.create(
            device=device, code_hash=hash_recovery_code(RECOVERY_CODE)
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
