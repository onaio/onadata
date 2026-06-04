"""Tests for failed-login lockout on the /accounts/login/ endpoint.

Covers locking out after MAX_LOGIN_ATTEMPTS failed attempts for LOCKOUT_TIME,
blocking all logins (even with the correct password) while locked, sending a
lockout email when the threshold is hit, and keying the lockout on IP + username.
"""

import sys
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.views.debug import ExceptionReporter, SafeExceptionReporterFilter

from onadata.apps.main.forms import LoginLockoutAuthenticationForm
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
        self.assertContains(response, "Invalid username or password")
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

    def test_lockout_not_bypassed_by_username_case(self):
        """Failed attempts with case variants count against the same account."""
        for username in ("bob", "BOB", "Bob"):
            self.client.post(self.url, {"username": username, "password": "wrong"})

        # Three failed attempts across case variants reach the threshold, so
        # even the correct password (and original casing) is now locked out.
        response = self._attempt(self.login_password)

        self.assertNotEqual(response.status_code, 302)
        self.assertContains(response, "Maximum login attempts exceeded")

    def test_lockout_not_bypassed_by_email_identifier(self):
        """Failed attempts via email count against the same account, and the
        lockout email is sent (it is looked up by canonical username)."""
        self.user.email = "bob@example.com"
        self.user.save()
        mail.outbox = []

        for _ in range(3):
            self.client.post(
                self.url, {"username": "bob@example.com", "password": "wrong"}
            )

        # The email-keyed attempts lock out the username login too.
        response = self._attempt(self.login_password)

        self.assertNotEqual(response.status_code, 302)
        self.assertContains(response, "Maximum login attempts exceeded")
        # Lockout email was dispatched despite the email-based identifier.
        self.assertTrue(mail.outbox)
        self.assertIn("bob@example.com", mail.outbox[0].to)


class LoginFormSensitiveVariablesTestCase(TestCase):
    """The overridden clean() must keep Django's @sensitive_variables()
    protection so the submitted password is scrubbed from error reports if
    validation raises unexpectedly (active when DEBUG is False, i.e. in
    production)."""

    def test_password_scrubbed_from_error_report(self):
        secret = "sup3r-s3cret-pw"  # nosec B105 - test fixture, not a real credential
        request = RequestFactory().post(
            "/accounts/login/", {"username": "bob", "password": secret}
        )
        form = LoginLockoutAuthenticationForm(
            request=request, data={"username": "bob", "password": secret}
        )

        # Force an unexpected error inside clean(), after the password local
        # has been bound, and capture the resulting traceback.
        with patch(
            "onadata.apps.main.forms.authenticate", side_effect=RuntimeError("boom")
        ):
            try:
                form.is_valid()
            except RuntimeError:
                exc_info = sys.exc_info()
            else:
                self.fail("expected RuntimeError to propagate from clean()")

        reporter = ExceptionReporter(request, *exc_info)
        password_locals = [
            value
            for frame in reporter.get_traceback_data()["frames"]
            for name, value in frame.get("vars", [])
            if name == "password"
        ]

        # The clean() frame did capture the password local ...
        self.assertTrue(password_locals)
        rendered = " ".join(str(value) for value in password_locals)
        # ... but it is cleansed, so the raw password never reaches the report.
        self.assertNotIn(secret, rendered)
        self.assertIn(SafeExceptionReporterFilter.cleansed_substitute, rendered)
