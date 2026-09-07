"""Tests for the login endpoints' session and lockout behaviour.

``/accounts/login/`` must never create a session: it only redirects to the
two-factor login wizard (``two_factor:login``), otherwise it would be a
password-only bypass of the second factor.

The failed-login lockout (``MAX_LOGIN_ATTEMPTS`` failed attempts locks the
account for ``LOCKOUT_TIME``, keyed on IP + username, with a lockout email at
the threshold) is enforced on both of the wizard's steps: covering only the
credentials step would leave whoever holds the password an unbounded run at
the six-digit code.
"""

import re
import sys
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.shortcuts import resolve_url
from django.test import (
    Client,
    RequestFactory,
    SimpleTestCase,
    TestCase,
    override_settings,
)
from django.urls import NoReverseMatch, reverse
from django.views.debug import ExceptionReporter, SafeExceptionReporterFilter

from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from formtools.wizard.views import normalize_name

from onadata.apps.main.forms import LoginLockoutAuthenticationForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.two_factor_views import LockoutLoginView

#: formtools prefixes wizard fields with the view's normalised class name, so
#: renaming the view would silently break every post below unless this follows.
STEP_FIELD = f"{normalize_name(LockoutLoginView.__name__)}-current_step"


class WizardLogin:
    """Drives the login wizard, with no lockout state left behind.

    The lockout lives in the cache, which Django does not roll back between
    tests. Without clearing it a failed attempt in one test locks the shared
    user out for LOCKOUT_TIME in every test that follows -- and, against a real
    cache, in the next run too.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        self.url = reverse("two_factor:login")
        self.client = Client()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def submit_credentials(self, password=None, username=None):
        return self.client.post(
            self.url,
            {
                STEP_FIELD: "auth",
                "auth-username": username or self.user.username,
                "auth-password": password or self.login_password,
            },
        )

    def submit_token(self, token):
        return self.client.post(
            self.url, {STEP_FIELD: "token", "token-otp_token": token}
        )

    def enrol_device(self):
        return TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)

    def current_token(self, device):
        # Zero-padded: oath.totp returns an int, so a code beginning with 0
        # loses a digit and the wizard's six-character field rejects it as too
        # short -- one login in ten, which reads as a flaky test.
        return f"{totp(device.bin_key, device.step, device.t0):06d}"


class LoginUrlSettingTestCase(SimpleTestCase):
    """Upstream defaults must send login_required redirects to the wizard.

    A plain-login ``LOGIN_URL`` would bypass the second factor for every
    gated view — including django-oauth-toolkit's authorize view, which the
    OIDC login path relies on — so the default must point at the two-factor
    login and not depend on a deployment override.
    """

    def test_login_url_is_the_two_factor_wizard(self):
        # Imported as a module (not via active settings) so the assertion
        # holds even when a deployment settings module overrides LOGIN_URL.
        from onadata.settings import common

        self.assertEqual(common.LOGIN_URL, "two_factor:login")
        self.assertEqual(resolve_url(common.LOGIN_URL), reverse("two_factor:login"))


class ManagementRoutesTestCase(SimpleTestCase):
    """Only login is routed; the API owns the rest -- see ``two_factor_urls``."""

    def test_no_management_or_enrolment_route_resolves(self):
        """Covers the package's whole URLConf, not just what it ships today.

        ``profile`` and ``disable`` live in ``two_factor.urls.profile`` and
        the rest in ``.core``; neither module is included here, so these names
        have never resolved. Asserted anyway: including either module, or
        ``two_factor.urls`` wholesale, would route them in one line.
        """
        for name in ("profile", "disable", "backup_tokens", "setup", "qr"):
            with self.subTest(route=name):
                with self.assertRaises(NoReverseMatch):
                    reverse(f"two_factor:{name}")

    def test_enrolment_completion_has_no_route(self):
        """Named apart from the rest because setup_complete is where SetupView
        lands: serving it would render a template that reverses
        ``two_factor:profile``, which resolves nowhere here."""
        with self.assertRaises(NoReverseMatch):
            reverse("two_factor:setup_complete")

    def test_login_is_routed_at_its_own_path(self):
        """The path is declared by this project, so it is asserted here rather
        than inherited from whatever the package currently uses."""
        self.assertEqual(reverse("two_factor:login"), "/account/login/")


class AccountsLoginRedirectTestCase(WizardLogin, TestBase):
    """``/accounts/login/`` redirects to the wizard and never authenticates."""

    def setUp(self):
        super().setUp()
        self.url = reverse("auth_login")

    def test_get_redirects_to_two_factor_login(self):
        response = self.client.get(self.url)

        self.assertRedirects(
            response, reverse("two_factor:login"), fetch_redirect_response=False
        )

    def test_redirect_preserves_next_parameter(self):
        response = self.client.get(self.url, {"next": "/bob/bob"})

        self.assertRedirects(
            response,
            reverse("two_factor:login") + "?next=/bob/bob",
            fetch_redirect_response=False,
        )

    def test_post_with_valid_credentials_does_not_create_session(self):
        """Posting valid credentials must not log the user in.

        This is the password-only 2FA bypass: a session minted here would
        skip the wizard's token step entirely.
        """
        response = self.client.post(
            self.url,
            {"username": self.user.username, "password": self.login_password},
        )

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)


class EnrolledUserWizardTestCase(WizardLogin, TestBase):
    """An enrolled user is challenged for a token and only completes login
    after providing one.

    Driven end to end rather than against the forms, so a step-name typo or an
    upstream ``form_list`` change cannot pass here.
    """

    def setUp(self):
        super().setUp()
        self.device = self.enrol_device()

    def test_credentials_alone_do_not_establish_a_session(self):
        """Correct username and password advance to the token step without
        logging the user in -- the whole point of the second factor."""
        response = self.submit_credentials()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_valid_token_completes_login(self):
        self.submit_credentials()

        response = self.submit_token(self.current_token(self.device))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))

    def test_wrong_token_does_not_establish_a_session(self):
        self.submit_credentials()

        response = self.submit_token("000000")

        self.assertNotEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)


class WizardVerificationAuditTestCase(WizardLogin, TestBase):
    """A failed wizard token entry reaches the security audit log.

    The same action the API's failed checks record: one event, both doors.
    """

    def setUp(self):
        super().setUp()
        self.device = self.enrol_device()

    def test_failed_token_is_written_to_the_security_audit_log(self):
        self.submit_credentials()

        with self.assertLogs("audit_logger", level="DEBUG") as captured:
            response = self.submit_token("000000")

        self.assertNotEqual(response.status_code, 302)
        actions = {
            getattr(record, "formhub_action", None) for record in captured.records
        }
        self.assertIn("two-factor-verification-failed", actions)

    def test_a_valid_token_is_not_recorded_as_a_failure(self):
        self.submit_credentials()

        with self.assertNoLogs("audit_logger", level="DEBUG"):
            response = self.submit_token(self.current_token(self.device))

        self.assertEqual(response.status_code, 302)


@override_settings(MAX_LOGIN_ATTEMPTS=3, LOCKOUT_TIME=1800)
class TokenStepLockoutTestCase(WizardLogin, TestBase):
    """The lockout covers the token step, not the credentials step alone.

    Upstream applies it to the first step only, which leaves whoever already
    holds the password an effectively unbounded run at a six-digit code.
    django-otp throttles each device, but that backoff is per device and tells
    the account holder nothing -- no lockout, no lockout email.
    """

    def setUp(self):
        super().setUp()
        self.device = self.enrol_device()
        self.submit_credentials()

    def test_wrong_tokens_lock_the_account_out(self):
        for _ in range(settings.MAX_LOGIN_ATTEMPTS):
            self.submit_token("000000")

        response = self.submit_token(self.current_token(self.device))

        self.assertNotEqual(response.status_code, 302)
        self.assertContains(response, "Maximum login attempts exceeded")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_the_lockout_is_shared_with_the_credentials_step(self):
        """Both steps count against one key.

        Two separate budgets would let an attacker spend the full allowance on
        passwords and then the full allowance again on codes -- so the counts
        below are split across the two steps and add up to one allowance.
        """
        wrong_passwords = settings.MAX_LOGIN_ATTEMPTS - 1
        for _ in range(wrong_passwords):
            self.submit_credentials(password="wrong-password")
        self.submit_credentials()

        self.submit_token("000000")  # the attempt that reaches the threshold
        response = self.submit_token(self.current_token(self.device))

        self.assertContains(response, "Maximum login attempts exceeded")
        self.assertNotIn("_auth_user_id", self.client.session)


@override_settings(TWO_FACTOR_REMEMBER_COOKIE_AGE=60 * 60 * 24 * 30)
class RememberDeviceOptInTestCase(WizardLogin, TestBase):
    """Skipping the second factor for a month has to be chosen, not defaulted.

    django-two-factor-auth adds the field with ``initial=True`` whenever an age
    is configured, so submitting the token step without reading it would buy a
    month-long bypass.
    """

    def test_the_token_step_offers_remember_unchecked(self):
        """Asserted on the rendered page rather than the form object: the
        checkbox the user actually sees is the thing that must not be ticked,
        and the form class is chosen by the plugin registry at request time.
        """
        self.enrol_device()

        response = self.submit_credentials()

        body = response.content.decode()
        tag = re.search(r'<input[^>]*name="token-remember"[^>]*>', body)
        self.assertIsNotNone(tag, "the remember checkbox is not on the page")
        self.assertNotIn("checked", tag.group(0))


@override_settings(MAX_LOGIN_ATTEMPTS=3, LOCKOUT_TIME=1800)
class TwoFactorLoginLockoutTestCase(WizardLogin, TestBase):
    """Lockout behaviour for the two-factor login wizard's credentials step."""

    def _attempt(self, password, username=None):
        return self.submit_credentials(password=password, username=username)

    def test_login_succeeds_without_second_factor_device(self):
        """Valid credentials for a user with no OTP device complete the
        wizard in one step and establish a session."""
        response = self._attempt(self.login_password)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))

    def test_locks_out_after_max_attempts(self):
        """Correct password is blocked once MAX_LOGIN_ATTEMPTS is reached."""
        for _ in range(3):
            self._attempt("wrong-password")

        response = self._attempt(self.login_password)

        self.assertNotEqual(response.status_code, 302)
        self.assertContains(response, "Maximum login attempts exceeded")
        self.assertNotIn("_auth_user_id", self.client.session)

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

        response = self._attempt("alicepass", username="alice")

        self.assertEqual(response.status_code, 302)
        alice = User.objects.get(username="alice")
        self.assertEqual(self.client.session.get("_auth_user_id"), str(alice.pk))

    def test_lockout_not_bypassed_by_username_case(self):
        """Failed attempts with case variants count against the same account."""
        for username in ("bob", "BOB", "Bob"):
            self._attempt("wrong", username=username)

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
            self._attempt("wrong", username="bob@example.com")

        response = self._attempt(self.login_password)

        self.assertNotEqual(response.status_code, 302)
        self.assertContains(response, "Maximum login attempts exceeded")
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
