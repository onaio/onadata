# -*- coding: utf-8 -*-
"""
Tests for the step-up gate on pages that write gated values.
"""

from django.test import override_settings
from django.urls import reverse

from django_otp.plugins.otp_totp.models import TOTPDevice
from oidc.stepup_grants import issue_grant

from onadata.apps.main.models import UserProfile
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.views import profile_settings

GATED = {
    "MODE": "local",
    "ACTIONS": {"change-email", "require-auth-toggle", "change-password"},
    "NO_FACTOR_POLICY": "skip_gate",
}

EMAIL = "bob@example.org"
NEW_EMAIL = "somewhere.else@example.org"
NEW_PASSWORD = "Tr0ub4dor-and-3-horses"


@override_settings(STEP_UP=GATED)
class TestProfileSettingsPageGate(TestBase):
    """The settings page writes email and require_auth, so it must not be a
    way around the API's gates."""

    def setUp(self):
        super().setUp()
        # The form requires an email, and TestBase's user has none: without
        # one every post fails validation before reaching the gate.
        self.user.email = EMAIL
        self.user.save()
        # Enrolled, because skip_gate lets a user with no factor through.
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self.url = reverse(profile_settings, kwargs={"username": self.user.username})

    def _post(self, data):
        """Post the form as rendered: every gated value as stored unless
        ``data`` changes it."""
        profile = UserProfile.objects.get(user=self.user)
        return self.client.post(
            self.url,
            {
                "name": "Bobby",
                "email": EMAIL,
                "require_auth": profile.require_auth,
                **data,
            },
        )

    def test_changing_the_email_without_a_grant_is_refused(self):
        response = self._post({"email": NEW_EMAIL})

        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, EMAIL)

    def test_changing_require_auth_without_a_grant_is_refused(self):
        before = UserProfile.objects.get(user=self.user).require_auth

        response = self._post({"require_auth": not before})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(UserProfile.objects.get(user=self.user).require_auth, before)

    def test_an_edit_changing_no_gated_value_is_saved(self):
        response = self._post({"city": "Bobville"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(UserProfile.objects.get(user=self.user).city, "Bobville")

    def test_a_grant_in_the_form_lets_the_email_change_through(self):
        grant = issue_grant(self.user.pk, "change-email")

        response = self._post({"email": NEW_EMAIL, "grant": grant})

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, NEW_EMAIL)


@override_settings(STEP_UP=GATED)
class TestPasswordChangePageGate(TestBase):
    """The password page changes the password as the API's change_password
    does, so it is gated the same way."""

    def setUp(self):
        super().setUp()
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self.url = reverse("auth_password_change")

    def _post(self, data=None):
        return self.client.post(
            self.url,
            {
                "old_password": self.login_password,
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
                **(data or {}),
            },
        )

    def test_changing_the_password_without_a_grant_is_refused(self):
        response = self._post()

        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.login_password))

    def test_a_grant_lets_the_password_change_through(self):
        grant = issue_grant(self.user.pk, "change-password")

        response = self._post({"grant": grant})

        self.assertRedirects(
            response,
            reverse("auth_password_change_done"),
            fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
