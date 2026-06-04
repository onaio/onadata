"""Tests for failed-login lockout on the /accounts/login/ endpoint.

The lockout must mirror the behaviour already enforced by the digest
authentication flow (onadata.libs.authentication): lock out after
MAX_LOGIN_ATTEMPTS failed attempts for LOCKOUT_TIME, block all logins
(even with the correct password) while locked, send a lockout email when
the threshold is hit, and key the lockout on IP + username.
"""

from django.core import mail
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse

from onadata.apps.main.tests.test_base import TestBase


@override_settings(MAX_LOGIN_ATTEMPTS=3, LOCKOUT_TIME=1800)
class AccountsLoginLockoutTestCase(TestBase):
    """Lockout behaviour for POST /accounts/login/."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.url = reverse("auth_login")
        self.client = Client()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def _attempt(self, password):
        return self.client.post(
            self.url, {"username": self.user.username, "password": password}
        )

    def test_locks_out_after_max_attempts(self):
        """Correct password is blocked once MAX_LOGIN_ATTEMPTS is reached."""
        for _ in range(3):
            self._attempt("wrong-password")

        response = self._attempt(self.login_password)

        # Locked out: the form is re-rendered (not a login redirect) and
        # shows the lockout message.
        self.assertNotEqual(response.status_code, 302)
        self.assertContains(response, "Maximum login attempts exceeded")

    def test_failed_attempt_shows_generic_error(self):
        """A failed attempt below the threshold shows a generic error and
        does not disclose the number of remaining attempts."""
        response = self._attempt("wrong-password")

        self.assertNotEqual(response.status_code, 302)
        self.assertContains(response, "Invalid username/password")
        self.assertNotContains(response, "more failed")

    def test_lockout_email_sent_at_threshold(self):
        """A lockout email is sent when the lockout threshold is reached."""
        self.user.email = "bob@example.com"
        self.user.save()
        mail.outbox = []

        for _ in range(3):
            self._attempt("wrong-password")

        self.assertTrue(mail.outbox)
        self.assertIn("bob@example.com", mail.outbox[0].to)

    def test_lockout_is_keyed_per_username(self):
        """Locking out one user does not lock out another from the same IP."""
        self._create_user("alice", "alicepass", create_profile=True)

        for _ in range(3):
            self._attempt("wrong-password")  # locks out bob

        response = self.client.post(
            self.url, {"username": "alice", "password": "alicepass"}
        )

        self.assertEqual(response.status_code, 302)
