# -*- coding: utf-8 -*-
"""Tests for the recovery-code step of the login wizard."""
from django.test import Client
from django.urls import reverse

from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from formtools.wizard.views import normalize_name

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.two_factor_views import LockoutLoginView

STEP_FIELD = f"{normalize_name(LockoutLoginView.__name__)}-current_step"

RECOVERY_CODE = "abcd2345"


class RecoveryCodeStepTestCase(TestBase):
    """The wizard's recovery-code step accepts and explains recovery codes.

    Codes are stored lowercase (``StaticToken.random_token`` lowercases its
    base32), and the library compares them exactly. Phone keyboards
    autocapitalise, so a user typing the code they were shown would be told it
    was wrong; the API relay already lowercases, and these pin the wizard to
    the same behaviour.
    """

    def setUp(self):
        super().setUp()
        self.url = reverse("two_factor:login")
        self.client = Client()
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        device = StaticDevice.objects.create(
            user=self.user, name="backup", confirmed=True
        )
        StaticToken.objects.create(device=device, token=RECOVERY_CODE)

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
        """A code typed in caps is accepted, matching the API relay."""
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
