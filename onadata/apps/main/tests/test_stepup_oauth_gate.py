# -*- coding: utf-8 -*-
"""
Tests for the step-up gate on approving, registering or redirecting an OAuth
application.
"""

import base64
import hashlib
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from django_otp.plugins.otp_totp.models import TOTPDevice
from oauth2_provider.models import AccessToken, Grant, get_application_model
from oidc.stepup_grants import issue_grant, spend_grant

AUTHORIZE_OAUTH_APP = "authorize-oauth-app"
STEP_UP_ON = {
    "MODE": "local",
    "ACTIONS": [AUTHORIZE_OAUTH_APP],
    "NO_FACTOR_POLICY": "skip_gate",
}
STEP_UP_OFF = {**STEP_UP_ON, "ACTIONS": []}

AUTHORIZE_URL = "/o/authorize/"
REGISTER_URL = "/o/applications/register/"
REDIRECT_URI = "https://client.example.test/oauth/callback"
OTHER_REDIRECT_URI = "https://elsewhere.example.test/oauth/callback"
VERIFIER = "v" * 43


def _challenge():
    digest = hashlib.sha256(VERIFIER.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _query(response):
    return parse_qs(urlparse(response["Location"]).query)


class StepUpOAuthTestCase(TestCase):
    """A logged-in user with a confirmed factor, and helpers for the OAuth
    pages."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(username="oauth-gate-user")
        cls.app_owner = user_model.objects.create_user(username="oauth-app-owner")

    def setUp(self):
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self.client.force_login(self.user)

    def _application(self, **overrides):
        application_model = get_application_model()
        fields = {
            "user": self.app_owner,
            "name": "Third-party application",
            "client_type": application_model.CLIENT_PUBLIC,
            "authorization_grant_type": application_model.GRANT_AUTHORIZATION_CODE,
            "redirect_uris": REDIRECT_URI,
            **overrides,
        }
        return application_model.objects.create(**fields)

    @staticmethod
    def _authorization(application):
        return {
            "client_id": application.client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "read",
            "state": "safe-state",
            "code_challenge": _challenge(),
            "code_challenge_method": "S256",
        }

    def _approve(self, application, **extra):
        return self.client.post(
            AUTHORIZE_URL, {**self._authorization(application), "allow": True, **extra}
        )

    @staticmethod
    def _registration(**overrides):
        application_model = get_application_model()
        return {
            "name": "Registered application",
            "client_id": "registered-client",
            "client_type": application_model.CLIENT_PUBLIC,
            "authorization_grant_type": application_model.GRANT_AUTHORIZATION_CODE,
            "redirect_uris": OTHER_REDIRECT_URI,
            "post_logout_redirect_uris": "",
            "allowed_origins": "",
            "algorithm": "",
            **overrides,
        }

    def _update(self, application, **changes):
        data = self._registration(
            name=application.name,
            client_id=application.client_id,
            client_type=application.client_type,
            redirect_uris=application.redirect_uris,
        )
        return self.client.post(
            f"/o/applications/{application.pk}/update/", {**data, **changes}
        )

    def _grant(self):
        return issue_grant(self.user.pk, AUTHORIZE_OAUTH_APP)

    def _codes(self, application):
        return Grant.objects.filter(application=application, user=self.user)


@override_settings(STEP_UP=STEP_UP_ON)
class TestApprovingAnOAuthApplication(StepUpOAuthTestCase):
    """Approving an application issues it a long-lived credential, so a
    stolen session alone must not be able to."""

    def test_approving_without_a_grant_is_refused(self):
        application = self._application()
        consent = self.client.get(AUTHORIZE_URL, self._authorization(application))
        self.assertEqual(consent.status_code, 200)

        response = self._approve(application)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(self._codes(application).exists())
        self.assertFalse(AccessToken.objects.filter(application=application).exists())

    def test_a_grant_for_another_action_is_refused(self):
        application = self._application()

        response = self._approve(
            application, grant=issue_grant(self.user.pk, "change-email")
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(self._codes(application).exists())

    def test_a_grant_lets_the_approval_through(self):
        application = self._application()
        grant = self._grant()

        response = self._approve(application, grant=grant)

        self.assertEqual(response.status_code, 302)
        self.assertIn("code", _query(response))
        self.assertTrue(self._codes(application).exists())
        self.assertFalse(spend_grant(self.user.pk, AUTHORIZE_OAUTH_APP, grant))

    def test_denying_is_not_challenged(self):
        application = self._application()

        response = self.client.post(AUTHORIZE_URL, self._authorization(application))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(_query(response)["error"], ["access_denied"])
        self.assertFalse(self._codes(application).exists())

    def test_an_invalid_approval_keeps_the_grant(self):
        """The form validates first, so a tampered request does not spend it."""
        application = self._application()
        grant = self._grant()
        data = {**self._authorization(application), "allow": True, "grant": grant}
        del data["client_id"]

        response = self.client.post(AUTHORIZE_URL, data)

        self.assertNotEqual(response.status_code, 302)
        self.assertFalse(self._codes(application).exists())
        self.assertTrue(spend_grant(self.user.pk, AUTHORIZE_OAUTH_APP, grant))

    def test_skip_authorization_falls_back_to_the_consent_form(self):
        application = self._application(skip_authorization=True)
        self.assertTrue(application.skip_authorization)

        response = self.client.get(AUTHORIZE_URL, self._authorization(application))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="allow"')
        self.assertFalse(self._codes(application).exists())

    def test_a_matching_token_falls_back_to_the_consent_form(self):
        application = self._application()
        AccessToken.objects.create(
            user=self.user,
            application=application,
            token="existing-access-token",
            expires=timezone.now() + timedelta(hours=1),
            scope="read",
        )
        data = {**self._authorization(application), "approval_prompt": "auto"}

        response = self.client.get(AUTHORIZE_URL, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="allow"')
        self.assertFalse(self._codes(application).exists())

    def test_a_header_grant_lets_auto_approval_through(self):
        application = self._application(skip_authorization=True)
        grant = self._grant()

        response = self.client.get(
            AUTHORIZE_URL,
            self._authorization(application),
            HTTP_X_STEP_UP_GRANT=grant,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("code", _query(response))
        self.assertFalse(spend_grant(self.user.pk, AUTHORIZE_OAUTH_APP, grant))


@override_settings(STEP_UP=STEP_UP_ON)
class TestRegisteringAnOAuthApplication(StepUpOAuthTestCase):
    """Registering an application, or pointing one at new redirect URIs,
    lets whoever holds the session collect the codes it is issued."""

    def _registered(self):
        return get_application_model().objects.filter(user=self.user)

    def test_registering_without_a_grant_is_refused(self):
        self.assertFalse(self._registered().exists())

        response = self.client.post(REGISTER_URL, self._registration())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(self._registered().exists())

    def test_a_grant_lets_the_registration_through(self):
        grant = self._grant()

        response = self.client.post(REGISTER_URL, self._registration(grant=grant))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(self._registered().values_list("redirect_uris", flat=True)),
            [OTHER_REDIRECT_URI],
        )
        self.assertFalse(spend_grant(self.user.pk, AUTHORIZE_OAUTH_APP, grant))

    def test_an_invalid_registration_keeps_the_grant(self):
        """Validation comes first, so a missing field does not spend it."""
        grant = self._grant()

        response = self.client.post(
            REGISTER_URL, self._registration(client_type="", grant=grant)
        )

        self.assertIn(response.status_code, (200, 400))
        self.assertFalse(self._registered().exists())
        self.assertTrue(spend_grant(self.user.pk, AUTHORIZE_OAUTH_APP, grant))

    def test_changing_redirect_uris_without_a_grant_is_refused(self):
        application = self._application(user=self.user)

        response = self._update(application, redirect_uris=OTHER_REDIRECT_URI)

        self.assertEqual(response.status_code, 403)
        application.refresh_from_db()
        self.assertEqual(application.redirect_uris, REDIRECT_URI)

    def test_changing_the_client_type_without_a_grant_is_refused(self):
        application_model = get_application_model()
        application = self._application(
            user=self.user, client_type=application_model.CLIENT_CONFIDENTIAL
        )

        response = self._update(
            application, client_type=application_model.CLIENT_PUBLIC
        )

        self.assertEqual(response.status_code, 403)
        application.refresh_from_db()
        self.assertEqual(application.client_type, application_model.CLIENT_CONFIDENTIAL)

    def test_a_grant_lets_the_redirect_change_through(self):
        application = self._application(user=self.user)
        grant = self._grant()

        response = self._update(
            application, redirect_uris=OTHER_REDIRECT_URI, grant=grant
        )

        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.redirect_uris, OTHER_REDIRECT_URI)
        self.assertFalse(spend_grant(self.user.pk, AUTHORIZE_OAUTH_APP, grant))

    def test_renaming_is_not_challenged(self):
        application = self._application(user=self.user)

        response = self._update(application, name="Renamed application")

        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.name, "Renamed application")
        self.assertEqual(application.redirect_uris, REDIRECT_URI)

    def test_deleting_is_not_challenged(self):
        application = self._application(user=self.user)

        response = self.client.post(f"/o/applications/{application.pk}/delete/")

        self.assertEqual(response.status_code, 302)
        self.assertFalse(self._registered().exists())


@override_settings(STEP_UP=STEP_UP_OFF)
class TestOAuthGateOff(StepUpOAuthTestCase):
    """A deployment that has not opted in behaves as before."""

    def test_approving_needs_no_grant(self):
        application = self._application()

        response = self._approve(application)

        self.assertEqual(response.status_code, 302)
        self.assertIn("code", _query(response))

    def test_skip_authorization_still_approves_on_get(self):
        application = self._application(skip_authorization=True)

        response = self.client.get(AUTHORIZE_URL, self._authorization(application))

        self.assertEqual(response.status_code, 302)
        self.assertIn("code", _query(response))

    def test_registering_needs_no_grant(self):
        response = self.client.post(REGISTER_URL, self._registration())

        self.assertEqual(response.status_code, 302)
        self.assertTrue(get_application_model().objects.filter(user=self.user).exists())
