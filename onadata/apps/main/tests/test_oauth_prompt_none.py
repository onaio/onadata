"""OpenID Connect ``prompt=none`` (silent authentication) acceptance tests."""

import base64
import hashlib
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from oauth2_provider.models import get_application_model


def _rsa_private_key_pem():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


OIDC_OAUTH2_PROVIDER = {
    **settings.OAUTH2_PROVIDER,
    "OIDC_ENABLED": True,
    "OIDC_RSA_PRIVATE_KEY": _rsa_private_key_pem(),
    "SCOPES": {**settings.OAUTH2_PROVIDER["SCOPES"], "openid": "OpenID Connect"},
}


@override_settings(
    OAUTH2_PROVIDER=OIDC_OAUTH2_PROVIDER,
    OIDC_PROMPT_NONE_ENABLED=True,
    OAUTH2_PKCE_S256_MODE="enforce",
    OAUTH2_PKCE_S256_MIGRATION_CUTOFF=None,
    OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT=None,
)
class OAuthPromptNoneTestCase(TestCase):
    """Prove silent authentication through the real authorization view."""

    redirect_uri = "https://client.example.test/oauth/callback"
    verifier = "v" * 43

    @classmethod
    def setUpTestData(cls):
        cls.resource_owner = get_user_model().objects.create_user(
            username="prompt-none-resource-owner",
            password="resource-owner-password",
        )

    @property
    def challenge(self):
        digest = hashlib.sha256(self.verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def _create_application(self, suffix, skip_authorization):
        application_model = get_application_model()
        owner = get_user_model().objects.create(
            username=f"prompt-none-app-owner-{suffix}",
            is_active=False,
        )
        owner.set_unusable_password()
        owner.save(update_fields=["password"])
        return application_model.objects.create(
            user=owner,
            name=f"Prompt none application {suffix}",
            client_id=f"prompt-none-client-{suffix}",
            client_secret=f"confidential-secret-{suffix}",
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_AUTHORIZATION_CODE,
            redirect_uris=self.redirect_uri,
            algorithm=application_model.RS256_ALGORITHM,
            skip_authorization=skip_authorization,
        )

    def _authorize_silently(self, application):
        return self.client.get(
            "/o/authorize/",
            {
                "client_id": application.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": "openid",
                "state": "safe-state",
                "nonce": "safe-nonce",
                "prompt": "none",
                "code_challenge": self.challenge,
                "code_challenge_method": "S256",
            },
        )

    def _redirect_parameters(self, response):
        self.assertEqual(response.status_code, 302)
        location = urlparse(response["Location"])
        self.assertEqual(
            f"{location.scheme}://{location.netloc}{location.path}",
            self.redirect_uri,
        )
        parameters = parse_qs(location.query)
        self.assertEqual(parameters["state"], ["safe-state"])
        return parameters

    def test_signed_in_user_of_a_skip_authorization_app_gets_a_code(self):
        application = self._create_application("skip", skip_authorization=True)
        self.client.force_login(self.resource_owner)

        parameters = self._redirect_parameters(self._authorize_silently(application))

        self.assertNotIn("error", parameters)
        self.assertIn("code", parameters)

    def test_app_that_needs_consent_gets_consent_required(self):
        application = self._create_application("consent", skip_authorization=False)
        self.client.force_login(self.resource_owner)

        parameters = self._redirect_parameters(self._authorize_silently(application))

        self.assertEqual(parameters["error"], ["consent_required"])
        self.assertNotIn("code", parameters)

    def test_anonymous_user_gets_login_required(self):
        application = self._create_application("anonymous", skip_authorization=True)

        parameters = self._redirect_parameters(self._authorize_silently(application))

        self.assertEqual(parameters["error"], ["login_required"])
        self.assertNotIn("code", parameters)

    def test_anonymous_user_of_an_app_that_needs_consent_gets_no_code(self):
        # The validator can't see the session, so consent is checked first:
        # still an interaction-required error, never a code.
        application = self._create_application(
            "anonymous-consent", skip_authorization=False
        )

        parameters = self._redirect_parameters(self._authorize_silently(application))

        self.assertEqual(parameters["error"], ["consent_required"])
        self.assertNotIn("code", parameters)

    @override_settings(OIDC_PROMPT_NONE_ENABLED=False)
    def test_signed_in_user_gets_login_required_when_disabled(self):
        application = self._create_application("disabled", skip_authorization=True)
        self.client.force_login(self.resource_owner)

        parameters = self._redirect_parameters(self._authorize_silently(application))

        self.assertEqual(parameters["error"], ["login_required"])
        self.assertNotIn("code", parameters)

    @override_settings(OIDC_PROMPT_NONE_ENABLED=False)
    def test_app_that_needs_consent_gets_login_required_when_disabled(self):
        application = self._create_application(
            "disabled-consent", skip_authorization=False
        )
        self.client.force_login(self.resource_owner)

        parameters = self._redirect_parameters(self._authorize_silently(application))

        self.assertEqual(parameters["error"], ["login_required"])
        self.assertNotIn("code", parameters)

    @override_settings(OIDC_PROMPT_NONE_ENABLED=False)
    def test_anonymous_user_gets_login_required_when_disabled(self):
        application = self._create_application(
            "disabled-anonymous", skip_authorization=True
        )

        parameters = self._redirect_parameters(self._authorize_silently(application))

        self.assertEqual(parameters["error"], ["login_required"])
        self.assertNotIn("code", parameters)
