"""
Tests for stepping up with an OAuth token at /api/v1/totp/verify.
"""

from datetime import timedelta
from types import SimpleNamespace

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from django_otp.util import random_hex
from oauth2_provider.models import AccessToken, get_application_model
from oauth2_provider.oauth2_validators import OAuth2Validator

from onadata.apps.api.models.encrypted_totp_device import EncryptedTOTPDevice
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tests.viewsets.test_totp_viewset import (
    TEST_ENCRYPTION_KEY,
    current_code,
    next_totp_window,
)
from onadata.apps.api.viewsets.totp_viewset import TOTP_DEVICE_NAME, TOTPViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.libs.authentication import MasterReplicaOAuth2Validator
from onadata.libs.stepup.policy import GATE_PRIVACY_CONSENT

ONLY_VERIFY = "OAuth applications can only verify a code."
NO_SCOPE = "This token lacks the stepup scope."
WRONG_AUDIENCE = "OAuth applications cannot verify for this audience."


@override_settings(
    ENABLE_TWO_FACTOR=True,
    STEP_UP={
        "MODE": "local",
        "ACTIONS": [GATE_PRIVACY_CONSENT],
        "NO_FACTOR_POLICY": "skip_gate",
    },
    TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[TEST_ENCRYPTION_KEY],
    # Pinned so the gated edit below does not depend on the environment.
    EU_CONSENT_METADATA_PATH=("client", "eu_citizen_consent"),
)
class TestOAuthStepUp(TestAbstractViewSet):
    """An OAuth application can earn a grant for a gated action, and nothing
    else, once the user has given it the stepup scope."""

    def setUp(self):
        super().setUp()
        # Lockout counters and grants live in the cache, which the test runner
        # does not roll back.
        cache.clear()
        self.addCleanup(cache.clear)
        self.device = EncryptedTOTPDevice(
            user=self.user, name=TOTP_DEVICE_NAME, confirmed=True
        )
        self.device.key = random_hex(20)
        self.device.save()

    def _bearer(self, scope):
        application_model = get_application_model()
        application = application_model.objects.create(
            name="stepup-app",
            user=self.user,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_AUTHORIZATION_CODE,
            redirect_uris="https://app.example/callback",
        )
        token = AccessToken.objects.create(
            user=self.user,
            application=application,
            token=f"stepup-access-{scope.replace(' ', '-')}",
            expires=timezone.now() + timedelta(hours=1),
            scope=scope,
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {token.token}"}

    def _post(self, handler, data, headers):
        view = TOTPViewSet.as_view({"post": handler})
        return view(self.factory.post("/", data=data, **headers))

    def _verify(self, headers, audience=GATE_PRIVACY_CONSENT, code=None):
        data = {"audience": audience, "code": code or current_code(self.device.key)}
        return self._post("verify", data, headers)

    def _set_consent(self, headers):
        consent = {
            "client": {
                "eu_citizen_consent": {
                    "is_collecting_eu_data": True,
                    "date": "2026-01-01T00:00:00Z",
                }
            }
        }
        view = UserProfileViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data={"metadata": consent}, format="json", **headers
        )
        return view(request, user=self.user.username)

    def test_a_scoped_token_earns_a_grant_its_gated_call_can_spend(self):
        """The whole round trip with one bearer token: challenged, verified,
        let through."""
        bearer = self._bearer("read write stepup")

        challenged = self._set_consent(bearer)
        self.assertEqual(challenged.status_code, 401, challenged.data)
        self.assertEqual(challenged.data["audience"], GATE_PRIVACY_CONSENT)

        with next_totp_window():
            verified = self._verify(bearer)
        self.assertEqual(verified.status_code, 200, verified.data)

        response = self._set_consent(
            {**bearer, "HTTP_X_STEP_UP_GRANT": verified.data["grant"]}
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_a_token_without_the_stepup_scope_is_refused_before_the_code(self):
        """Refused ahead of the check, so the user's code is still good for a
        caller allowed to use it. django-otp refuses a code already spent."""
        with next_totp_window():
            code = current_code(self.device.key)
            refused = self._verify(self._bearer("read write groups"), code=code)
            allowed = self._verify(self.extra, code=code)

        self.assertEqual(refused.status_code, 403)
        self.assertEqual(refused.data["detail"], NO_SCOPE)
        self.assertEqual(allowed.status_code, 200, allowed.data)

    def test_a_scoped_token_cannot_manage_the_second_factor(self):
        """Enrolling, disabling and the recovery codes stay with the user's
        own session or API token. The message shows the OAuth limit refused
        each one, not a check further in."""
        bearer = self._bearer("read write stepup")
        status_view = TOTPViewSet.as_view({"get": "totp_status"})
        with next_totp_window():
            code = current_code(self.device.key)
            for handler in (
                "enroll_start",
                "enroll_confirm",
                "disable",
                "recovery_generate",
                "recovery_view",
            ):
                with self.subTest(handler=handler):
                    response = self._post(handler, {"code": code}, bearer)
                    self.assertEqual(response.status_code, 403, response.data)
                    self.assertEqual(response.data["detail"], ONLY_VERIFY)
            response = status_view(self.factory.get("/", **bearer))

        self.assertEqual(response.status_code, 403, response.data)
        self.assertEqual(response.data["detail"], ONLY_VERIFY)
        self.assertTrue(
            EncryptedTOTPDevice.objects.filter(
                user=self.user, name=TOTP_DEVICE_NAME, confirmed=True
            ).exists()
        )

    def test_a_scoped_token_earns_no_grant_outside_the_gated_actions(self):
        """Not the management routes' audiences, nor an action that hands back
        a broader credential. The last call shows the code survived them."""
        bearer = self._bearer("read write stepup")
        with next_totp_window():
            code = current_code(self.device.key)
            for audience in (
                "disable",
                "recovery-view",
                "regenerate-api-key",
                "regenerate-odk-token",
                "authorize-oauth-app",
            ):
                with self.subTest(audience=audience):
                    response = self._verify(bearer, audience=audience, code=code)
                    self.assertEqual(response.status_code, 403, response.data)
                    self.assertEqual(response.data["detail"], WRONG_AUDIENCE)
            allowed = self._verify(bearer, code=code)

        self.assertEqual(allowed.status_code, 200, allowed.data)

    def test_the_stepup_scope_is_never_granted_by_default(self):
        """A request that names no scope gets the defaults; stepup has to be
        asked for, so it appears on the consent page."""
        request = SimpleNamespace(client=None)
        validator = MasterReplicaOAuth2Validator()

        everything = OAuth2Validator.get_default_scopes(validator, "client", request)
        defaults = validator.get_default_scopes("client", request)

        self.assertIn("stepup", everything)
        self.assertIn("read", defaults)
        self.assertNotIn("stepup", defaults)
