"""
Tests for stepping up with an OAuth token at /api/v1/totp/verify.
"""

from datetime import timedelta

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from django_otp.util import random_hex
from oauth2_provider.models import AccessToken, get_application_model
from registration.models import RegistrationProfile
from rest_framework.authtoken.models import Token

from onadata.apps.api.models.encrypted_totp_device import EncryptedTOTPDevice
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tests.viewsets.test_totp_viewset import (
    TEST_ENCRYPTION_KEY,
    current_code,
    next_totp_window,
)
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.apps.api.viewsets.totp_viewset import TOTP_DEVICE_NAME, TOTPViewSet
from onadata.libs.authentication import MasterReplicaOAuth2Validator
from onadata.libs.stepup.policy import GATE_REGENERATE_API_KEY


@override_settings(
    ENABLE_TWO_FACTOR=True,
    STEP_UP={
        "MODE": "local",
        "ACTIONS": [GATE_REGENERATE_API_KEY],
        "NO_FACTOR_POLICY": "skip_gate",
    },
    TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[TEST_ENCRYPTION_KEY],
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
        RegistrationProfile.objects.create_profile(self.user)
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

    def _verify(self, headers, audience=GATE_REGENERATE_API_KEY, code=None):
        data = {"audience": audience, "code": code or current_code(self.device.key)}
        return self._post("verify", data, headers)

    def test_a_scoped_token_earns_a_grant_its_gated_call_can_spend(self):
        """The whole round trip with one bearer token: challenged, verified,
        let through."""
        bearer = self._bearer("read write stepup")
        regenerate = ConnectViewSet.as_view({"get": "regenerate_auth_token"})
        old_token = Token.objects.get(user=self.user).key

        challenged = regenerate(self.factory.get("/", **bearer))
        self.assertEqual(challenged.status_code, 401, challenged.data)
        self.assertEqual(challenged.data["audience"], GATE_REGENERATE_API_KEY)

        with next_totp_window():
            verified = self._verify(bearer)
        self.assertEqual(verified.status_code, 200, verified.data)

        response = regenerate(
            self.factory.get("/", HTTP_X_STEP_UP_GRANT=verified.data["grant"], **bearer)
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotEqual(Token.objects.get(user=self.user).key, old_token)

    def test_a_token_without_the_stepup_scope_is_refused_before_the_code(self):
        """Refused ahead of the check, so the user's code is still good for a
        caller allowed to use it."""
        with next_totp_window():
            code = current_code(self.device.key)
            refused = self._verify(self._bearer("read write groups"), code=code)
            allowed = self._verify(self.extra, code=code)

        self.assertEqual(refused.status_code, 403)
        self.assertNotIn("grant", refused.data)
        self.assertEqual(allowed.status_code, 200, allowed.data)

    def test_a_scoped_token_cannot_manage_the_second_factor(self):
        """Enrolling, disabling and the recovery codes stay with the user's
        own session or API token."""
        bearer = self._bearer("read write stepup")
        with next_totp_window():
            code = current_code(self.device.key)
            for handler in (
                "enroll_start",
                "disable",
                "recovery_generate",
                "recovery_view",
            ):
                with self.subTest(handler=handler):
                    response = self._post(handler, {"code": code}, bearer)
                    self.assertEqual(response.status_code, 403, response.data)

        self.assertTrue(
            EncryptedTOTPDevice.objects.filter(
                user=self.user, name=TOTP_DEVICE_NAME, confirmed=True
            ).exists()
        )

    def test_a_scoped_token_cannot_earn_a_grant_for_a_management_route(self):
        bearer = self._bearer("read write stepup")

        with next_totp_window():
            response = self._verify(bearer, audience="disable")

        self.assertEqual(response.status_code, 403, response.data)
        self.assertNotIn("grant", response.data)

    def test_the_stepup_scope_is_never_granted_by_default(self):
        """A request that names no scope gets the defaults; stepup has to be
        asked for, so it appears on the consent page."""
        scopes = MasterReplicaOAuth2Validator().get_default_scopes("client", None)

        self.assertIn("read", scopes)
        self.assertNotIn("stepup", scopes)
