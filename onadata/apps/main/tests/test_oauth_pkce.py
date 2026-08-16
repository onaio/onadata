"""OAuth endpoint acceptance tests for the PKCE S256 policy."""

import base64
import hashlib
import json
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from oauth2_provider.models import (
    AccessToken,
    Grant,
    RefreshToken,
    get_application_model,
)


@override_settings(
    OAUTH2_PKCE_S256_MODE="enforce",
    OAUTH2_PKCE_S256_MIGRATION_CUTOFF=None,
    OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT=None,
)
class OAuthPKCEEndpointTestCase(TestCase):
    """Prove policy behavior through the real authorization and token views."""

    redirect_uri = "https://client.example.test/oauth/callback"
    verifier = "v" * 43

    @classmethod
    def setUpTestData(cls):
        cls.resource_owner = get_user_model().objects.create_user(
            username="pkce-resource-owner",
            password="resource-owner-password",
        )

    def setUp(self):
        self.client.force_login(self.resource_owner)

    @property
    def challenge(self):
        digest = hashlib.sha256(self.verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def _create_application(self, client_type, suffix, grant_type=None):
        application_model = get_application_model()
        owner = get_user_model().objects.create(
            username=f"pkce-app-owner-{suffix}",
            is_active=False,
        )
        owner.set_unusable_password()
        owner.save(update_fields=["password"])
        raw_secret = f"confidential-secret-{suffix}"
        application = application_model.objects.create(
            user=owner,
            name=f"PKCE application {suffix}",
            client_id=f"pkce-client-{suffix}",
            client_secret=raw_secret,
            client_type=client_type,
            authorization_grant_type=(
                grant_type or application_model.GRANT_AUTHORIZATION_CODE
            ),
            redirect_uris=self.redirect_uri,
            skip_authorization=False,
        )
        return application, raw_secret

    def _authorization_data(self, application, challenge=None, method=None):
        data = {
            "client_id": application.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "read",
            "state": "safe-state",
        }
        if challenge is not None:
            data["code_challenge"] = challenge
        if method is not None:
            data["code_challenge_method"] = method
        return data

    def _authorize(self, application, challenge=None, method=None):
        data = self._authorization_data(application, challenge, method)
        consent = self.client.get("/o/authorize/", data)
        self.assertEqual(consent.status_code, 200)

        data["allow"] = True
        response = self.client.post("/o/authorize/", data)
        self.assertEqual(response.status_code, 302)
        parameters = parse_qs(urlparse(response["Location"]).query)
        self.assertNotIn("error", parameters)
        return parameters["code"][0]

    def _token_data(self, application, code, verifier=None):
        data = {
            "grant_type": "authorization_code",
            "client_id": application.client_id,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        if verifier is not None:
            data["code_verifier"] = verifier
        return data

    @staticmethod
    def _basic_authorization(client_id, client_secret):
        credentials = f"{client_id}:{client_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(credentials).decode("ascii")

    def _exchange(
        self,
        application,
        raw_secret,
        code,
        verifier=None,
    ):
        headers = {}
        if application.client_type == application.CLIENT_CONFIDENTIAL:
            headers["HTTP_AUTHORIZATION"] = self._basic_authorization(
                application.client_id, raw_secret
            )
        return self.client.post(
            "/o/token/",
            self._token_data(application, code, verifier),
            **headers,
        )

    def _assert_oauth_redirect_error(self, response, expected_error):
        self.assertEqual(response.status_code, 302)
        parameters = parse_qs(urlparse(response["Location"]).query)
        self.assertEqual(parameters["error"], [expected_error])

    def test_public_and_confidential_s256_flows_succeed(self):
        application_model = get_application_model()
        for client_type in (
            application_model.CLIENT_PUBLIC,
            application_model.CLIENT_CONFIDENTIAL,
        ):
            with self.subTest(client_type=client_type):
                suffix = client_type
                application, raw_secret = self._create_application(client_type, suffix)
                code = self._authorize(
                    application,
                    challenge=self.challenge,
                    method="S256",
                )

                response = self._exchange(
                    application,
                    raw_secret,
                    code,
                    verifier=self.verifier,
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn("access_token", json.loads(response.content))
                self.assertTrue(
                    AccessToken.objects.filter(application=application).exists()
                )
                self.assertTrue(
                    RefreshToken.objects.filter(application=application).exists()
                )
                self.assertFalse(Grant.objects.filter(application=application).exists())

    def test_public_token_exchange_does_not_send_a_client_secret(self):
        application_model = get_application_model()
        application, raw_secret = self._create_application(
            application_model.CLIENT_PUBLIC, "public-no-secret"
        )
        code = self._authorize(application, self.challenge, "S256")

        response = self.client.post(
            "/o/token/",
            self._token_data(application, code, self.verifier),
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, raw_secret)

    def test_authorization_rejects_missing_or_non_s256_pkce_for_both_client_types(
        self,
    ):
        application_model = get_application_model()
        cases = (
            ("missing-challenge", None, None),
            ("missing-method", self.challenge, None),
            ("plain", self.verifier, "plain"),
            ("unsupported", self.challenge, "S512"),
        )
        for client_type in (
            application_model.CLIENT_PUBLIC,
            application_model.CLIENT_CONFIDENTIAL,
        ):
            for label, challenge, method in cases:
                with self.subTest(client_type=client_type, case=label):
                    application, _raw_secret = self._create_application(
                        client_type, f"{client_type}-{label}"
                    )

                    response = self.client.get(
                        "/o/authorize/",
                        self._authorization_data(application, challenge, method),
                    )

                    self._assert_oauth_redirect_error(response, "invalid_request")
                    self.assertFalse(
                        Grant.objects.filter(application=application).exists()
                    )

    def test_changed_hidden_pkce_method_is_rejected_without_a_grant(self):
        application_model = get_application_model()
        application, _raw_secret = self._create_application(
            application_model.CLIENT_PUBLIC, "changed-hidden-method"
        )
        data = self._authorization_data(application, self.challenge, "S256")
        self.assertEqual(self.client.get("/o/authorize/", data).status_code, 200)
        data.update({"allow": True, "code_challenge_method": "plain"})

        response = self.client.post("/o/authorize/", data)

        self._assert_oauth_redirect_error(response, "invalid_request")
        self.assertFalse(Grant.objects.filter(application=application).exists())

    def test_missing_and_wrong_verifiers_create_no_tokens(self):
        application_model = get_application_model()
        for client_type in (
            application_model.CLIENT_PUBLIC,
            application_model.CLIENT_CONFIDENTIAL,
        ):
            for label, verifier, expected_error in (
                ("missing", None, "invalid_request"),
                ("wrong", "w" * 43, "invalid_grant"),
            ):
                with self.subTest(client_type=client_type, case=label):
                    application, raw_secret = self._create_application(
                        client_type, f"{client_type}-verifier-{label}"
                    )
                    code = self._authorize(application, self.challenge, "S256")

                    response = self._exchange(
                        application,
                        raw_secret,
                        code,
                        verifier=verifier,
                    )

                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(
                        json.loads(response.content)["error"], expected_error
                    )
                    self.assertFalse(
                        AccessToken.objects.filter(application=application).exists()
                    )
                    self.assertFalse(
                        RefreshToken.objects.filter(application=application).exists()
                    )

    def _stored_grant(self, application, suffix, challenge="", method=""):
        return Grant.objects.create(
            user=self.resource_owner,
            application=application,
            code=f"stored-code-{suffix}",
            expires=timezone.now() + timedelta(minutes=1),
            redirect_uri=self.redirect_uri,
            scope="read",
            code_challenge=challenge,
            code_challenge_method=method,
        )

    def test_legacy_stored_grants_create_no_tokens(self):
        application_model = get_application_model()
        for client_type in (
            application_model.CLIENT_PUBLIC,
            application_model.CLIENT_CONFIDENTIAL,
        ):
            for label, challenge, method, verifier in (
                ("no-challenge", "", "", self.verifier),
                ("plain", self.verifier, "plain", self.verifier),
            ):
                with self.subTest(client_type=client_type, case=label):
                    application, raw_secret = self._create_application(
                        client_type, f"{client_type}-stored-{label}"
                    )
                    grant = self._stored_grant(
                        application,
                        f"{client_type}-{label}",
                        challenge,
                        method,
                    )

                    response = self._exchange(
                        application,
                        raw_secret,
                        grant.code,
                        verifier=verifier,
                    )

                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(
                        json.loads(response.content)["error"], "invalid_grant"
                    )
                    self.assertFalse(
                        AccessToken.objects.filter(application=application).exists()
                    )
                    self.assertFalse(
                        RefreshToken.objects.filter(application=application).exists()
                    )

    def test_active_legacy_window_preserves_prior_authorization_behavior(self):
        application_model = get_application_model()
        now = timezone.now()
        cutoff = now - timedelta(days=1)
        for client_type in (
            application_model.CLIENT_PUBLIC,
            application_model.CLIENT_CONFIDENTIAL,
        ):
            with self.subTest(client_type=client_type):
                application, raw_secret = self._create_application(
                    client_type, f"active-legacy-window-{client_type}"
                )
                application_model.objects.filter(pk=application.pk).update(
                    created=cutoff - timedelta(days=1)
                )
                application.refresh_from_db()
                with override_settings(
                    OAUTH2_PKCE_S256_MIGRATION_CUTOFF=cutoff,
                    OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT=(now + timedelta(days=1)),
                ):
                    code = self._authorize(application)
                    response = self._exchange(
                        application,
                        raw_secret,
                        code,
                    )

                self.assertEqual(response.status_code, 200)
                self.assertTrue(
                    AccessToken.objects.filter(application=application).exists()
                )

    def test_active_legacy_window_still_accepts_valid_s256(self):
        application_model = get_application_model()
        application, raw_secret = self._create_application(
            application_model.CLIENT_PUBLIC, "active-legacy-window-s256"
        )
        now = timezone.now()
        cutoff = now - timedelta(days=1)
        application_model.objects.filter(pk=application.pk).update(
            created=cutoff - timedelta(days=1)
        )
        application.refresh_from_db()
        with override_settings(
            OAUTH2_PKCE_S256_MIGRATION_CUTOFF=cutoff,
            OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT=now + timedelta(days=1),
        ):
            code = self._authorize(application, self.challenge, "S256")
            response = self._exchange(
                application,
                raw_secret,
                code,
                verifier=self.verifier,
            )

        self.assertEqual(response.status_code, 200)

    def test_expired_legacy_window_does_not_bypass_s256(self):
        application_model = get_application_model()
        now = timezone.now()
        cutoff = now - timedelta(days=1)
        for client_type in (
            application_model.CLIENT_PUBLIC,
            application_model.CLIENT_CONFIDENTIAL,
        ):
            with self.subTest(client_type=client_type):
                application, _raw_secret = self._create_application(
                    client_type, f"expired-legacy-window-{client_type}"
                )
                application_model.objects.filter(pk=application.pk).update(
                    created=cutoff - timedelta(days=1)
                )
                application.refresh_from_db()
                with override_settings(
                    OAUTH2_PKCE_S256_MIGRATION_CUTOFF=cutoff,
                    OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT=(now - timedelta(seconds=1)),
                ):
                    response = self.client.get(
                        "/o/authorize/",
                        self._authorization_data(application),
                    )

                self._assert_oauth_redirect_error(response, "invalid_request")
                self.assertFalse(Grant.objects.filter(application=application).exists())

    @override_settings(OAUTH2_PKCE_S256_MODE="observe")
    def test_observe_mode_preserves_prior_authorization_behavior(self):
        application_model = get_application_model()
        application, raw_secret = self._create_application(
            application_model.CLIENT_PUBLIC, "observe"
        )

        code = self._authorize(application)
        response = self._exchange(application, raw_secret, code)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(AccessToken.objects.filter(application=application).exists())
