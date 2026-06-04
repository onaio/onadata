# -*- coding: utf-8 -*-
"""Tests that organization accounts cannot establish a login session."""

from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponseRedirect
from django.test import RequestFactory, TestCase, override_settings

import jwt
from rest_framework import status

from onadata.apps.api.tools import create_organization
from onadata.apps.main.backends import ModelBackend
from onadata.apps.main.models import UserProfile
from onadata.apps.main.oidc_viewsets import OnaOpenIDConnectViewset
from onadata.libs.authentication import MasterReplicaOAuth2Validator

User = get_user_model()

# Fake, test-only login/credential values (not real secrets). Passed as
# variables rather than inline literals so static scanners don't flag them as
# hardcoded passwords.
TEST_CREDENTIAL = "login-value"
BEARER_VALUE = "bearer-value"
OIDC_AUTHORIZATION_ENDPOINT = "https://login.example.com/oauth2/v2.0/authorize"
OIDC_AUTH_SERVERS = {
    "microsoft": {
        "AUTHORIZATION_ENDPOINT": OIDC_AUTHORIZATION_ENDPOINT,
        "CLIENT_ID": "test-client-id",
        "JWKS_ENDPOINT": "https://login.example.com/discovery/keys",
        "SCOPE": "openid profile",
        "TOKEN_ENDPOINT": "https://login.example.com/oauth2/v2.0/token",
        "END_SESSION_ENDPOINT": "https://login.example.com/logout",
        "REDIRECT_URI": "http://testserver/oidc/microsoft/callback",
        "RESPONSE_TYPE": "id_token",
        "RESPONSE_MODE": "form_post",
        "USE_NONCES": False,
        "LOGIN_QUERY_PARAM_ALLOWLIST": ["kc_idp_hint"],
    }
}


class TestBlockOrgAccountLogin(TestCase):
    """Organization User rows hold permissions only; they must never log in."""

    def setUp(self):
        self.regular = User.objects.create_user(
            username="bob", password=TEST_CREDENTIAL, email="bob@example.com"
        )
        UserProfile.objects.create(user=self.regular)

        self.org = create_organization("denoinc", self.regular)
        self.org_user = self.org.user
        self.org_user.email = "org@example.com"
        self.org_user.set_password(TEST_CREDENTIAL)
        self.org_user.save()

    # -- Password backend ---------------------------------------------------

    def test_backend_rejects_org_user_by_username(self):
        backend = ModelBackend()
        self.assertIsNone(
            backend.authenticate(None, username="denoinc", password=TEST_CREDENTIAL)
        )

    def test_backend_rejects_org_user_by_email(self):
        backend = ModelBackend()
        self.assertIsNone(
            backend.authenticate(
                None, username="org@example.com", password=TEST_CREDENTIAL
            )
        )

    def test_backend_allows_regular_user_by_username(self):
        backend = ModelBackend()
        self.assertEqual(
            backend.authenticate(None, username="bob", password=TEST_CREDENTIAL),
            self.regular,
        )

    def test_backend_allows_regular_user_by_email(self):
        backend = ModelBackend()
        self.assertEqual(
            backend.authenticate(
                None, username="bob@example.com", password=TEST_CREDENTIAL
            ),
            self.regular,
        )

    def test_backend_allows_user_without_profile(self):
        # A valid password but no profile must not crash the org check.
        noprofile = User.objects.create_user(
            username="noprofile", password=TEST_CREDENTIAL
        )
        backend = ModelBackend()
        self.assertEqual(
            backend.authenticate(None, username="noprofile", password=TEST_CREDENTIAL),
            noprofile,
        )

    # -- OIDC SSO path ------------------------------------------------------

    @override_settings(OPENID_CONNECT_AUTH_SERVERS=OIDC_AUTH_SERVERS)
    def test_oidc_login_ignores_digest_auth_challenge_headers(self):
        response = self.client.get(
            "/oidc/microsoft/login?kc_idp_hint=onadata",
            HTTP_AUTHORIZATION='Digest username="stale", realm="api", nonce="bad"',
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertFalse(response.has_header("WWW-Authenticate"))

        redirect = urlparse(response["Location"])
        self.assertEqual(
            f"{redirect.scheme}://{redirect.netloc}{redirect.path}",
            OIDC_AUTHORIZATION_ENDPOINT,
        )
        self.assertEqual(parse_qs(redirect.query)["kc_idp_hint"], ["onadata"])

    @patch("oidc.viewsets.login")
    def test_oidc_rejects_org_user(self, mock_login):
        request = RequestFactory().get("/oidc/microsoft/callback")
        response = OnaOpenIDConnectViewset().generate_successful_response(
            request, self.org_user
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_login.assert_not_called()

    @patch("oidc.viewsets.login")
    def test_oidc_allows_regular_user(self, mock_login):
        request = RequestFactory().get("/oidc/microsoft/callback")
        response = OnaOpenIDConnectViewset().generate_successful_response(
            request, self.regular
        )
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

    # -- Bearer token (defensive) ------------------------------------------

    def test_validate_bearer_token_rejects_org_user(self):
        self.assertFalse(self._validate_token_for(self.org_user))

    def test_validate_bearer_token_allows_regular_user(self):
        request, result = self._validate_token_for(self.regular, return_request=True)
        self.assertTrue(result)
        self.assertEqual(request.user, self.regular)

    @staticmethod
    def _validate_token_for(user, return_request=False):
        token = MagicMock()
        token.is_valid.return_value = True
        token.user = user
        token.application = "app"
        token.token = BEARER_VALUE
        request = HttpRequest()
        with patch("onadata.libs.authentication.AccessToken") as mock_token_class:
            mock_token_class.objects.select_related(
                "application", "user"
            ).get.return_value = token
            result = MasterReplicaOAuth2Validator().validate_bearer_token(
                BEARER_VALUE, {}, request
            )
        if return_request:
            return request, result
        return result


SESSION_VIEWSET_CONFIG = {
    "JWT_SECRET_KEY": "test-sso-secret-for-session-endpoint",
    "JWT_ALGORITHM": "HS256",
}


@override_settings(OPENID_CONNECT_VIEWSET_CONFIG=SESSION_VIEWSET_CONFIG)
class TestOIDCSessionEndpoint(TestCase):
    """The challenge-free ``/oidc/<server>/session`` reload-restore probe."""

    def setUp(self):
        self.regular = User.objects.create_user(
            username="bob", password=TEST_CREDENTIAL, email="bob@example.com"
        )
        self.profile = UserProfile.objects.create(
            user=self.regular, name="Bob Tester", require_auth=True
        )
        self.org = create_organization("denoinc", self.regular)
        self.org_user = self.org.user
        self.org_user.email = "org@example.com"
        self.org_user.save()

    def _sso_cookie(self, email):
        return jwt.encode(
            {"email": email},
            SESSION_VIEWSET_CONFIG["JWT_SECRET_KEY"],
            algorithm="HS256",
        )

    def _get_session(self, email=None, **extra):
        if email is not None:
            self.client.cookies["SSO"] = self._sso_cookie(email)
        return self.client.get("/oidc/microsoft/session", **extra)

    def test_valid_session_returns_profile_without_secrets(self):
        response = self._get_session("bob@example.com")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["username"], "bob")
        self.assertEqual(data["name"], "Bob Tester")
        self.assertEqual(data["require_auth"], True)
        self.assertIn("gravatar", data)
        # No PII / no token material leaves the endpoint.
        self.assertNotIn("email", data)
        self.assertNotIn("api_token", data)
        self.assertNotIn("temp_token", data)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertFalse(response.has_header("WWW-Authenticate"))

    def test_anonymous_request_returns_plain_401(self):
        response = self._get_session()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.json())
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertFalse(response.has_header("WWW-Authenticate"))

    def test_html_accept_header_cannot_negotiate_template_renderer(self):
        response = self._get_session(HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)
        self.assertIn("detail", response.json())
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertFalse(response.has_header("WWW-Authenticate"))

    def test_invalid_sso_cookie_returns_plain_401(self):
        self.client.cookies["SSO"] = "not-a-jwt"
        response = self.client.get("/oidc/microsoft/session")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.json())
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertFalse(response.has_header("WWW-Authenticate"))

    def test_org_account_is_rejected(self):
        response = self._get_session("org@example.com")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertFalse(response.has_header("WWW-Authenticate"))

    def test_digest_authorization_header_does_not_challenge(self):
        response = self.client.get(
            "/oidc/microsoft/session",
            HTTP_AUTHORIZATION='Digest username="stale", realm="api", nonce="bad"',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertFalse(response.has_header("WWW-Authenticate"))


class TestOIDCLoginStaleCookieCleanup(TestCase):
    """OIDC ``login`` must evict stale auth cookies on entry."""

    @override_settings(OPENID_CONNECT_AUTH_SERVERS=OIDC_AUTH_SERVERS)
    def test_login_redirect_carries_session_cookie_deletion(self):
        response = self.client.get("/oidc/microsoft/login")
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        cookie = response.cookies.get("sessionid")
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie["max-age"], 0)

    @override_settings(OPENID_CONNECT_AUTH_SERVERS=OIDC_AUTH_SERVERS)
    def test_login_redirect_carries_sso_cookie_deletion(self):
        response = self.client.get("/oidc/microsoft/login")
        cookie = response.cookies.get("SSO")
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie["max-age"], 0)

    @override_settings(OPENID_CONNECT_AUTH_SERVERS=OIDC_AUTH_SERVERS)
    def test_login_redirect_carries_messages_cookie_deletion(self):
        response = self.client.get("/oidc/microsoft/login")
        cookie = response.cookies.get("messages")
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie["max-age"], 0)

    @override_settings(OPENID_CONNECT_AUTH_SERVERS=OIDC_AUTH_SERVERS)
    def test_login_still_deletes_csrftoken_from_base_viewset(self):
        response = self.client.get("/oidc/microsoft/login")
        cookie = response.cookies.get("csrftoken")
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie["max-age"], 0)
