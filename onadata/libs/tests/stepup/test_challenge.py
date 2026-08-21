# -*- coding: utf-8 -*-
"""Tests for the challenge body and the DRF gate."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from onadata.libs.stepup.challenge import build_challenge
from onadata.libs.stepup.drf import RequiresStepUp
from oidc.stepup_grants import issue_grant

GATED = {"ACTIONS": {"require-auth-toggle"}, "MODE": "local"}


class TestChallenge(TestCase):
    @override_settings(STEP_UP=GATED)
    def test_local_mode_asks_for_a_code(self):
        body = build_challenge("require-auth-toggle")

        self.assertEqual(body["error"], "step_up_required")
        self.assertEqual(body["dialect"], "local-totp")
        # The audience the client echoes to /totp/verify. Without it the grant
        # it gets back is not spendable here.
        self.assertEqual(body["audience"], "require-auth-toggle")


class _View(RequiresStepUp):
    pass


class _GateHarness(TestCase):
    """Shared setup for both gate suites.

    A DRF Request with an explicit parser, because the gate reads
    ``request.data`` and one built without parsers raises UnsupportedMediaType
    rather than returning the grant.
    """

    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create(
            username="ana", email="ana@example.org"
        )
        self.view = _View()

    def _request(self, data=None):
        request = Request(
            self.factory.post("/", data or {}, format="json"),
            parsers=[JSONParser()],
        )
        request.user = self.user
        return request


class TestRequiresStepUp(_GateHarness):
    def _enrol(self):
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)

    @override_settings(STEP_UP=GATED)
    def test_an_enrolled_user_without_a_grant_is_challenged(self):
        self._enrol()

        refusal = self.view.check_step_up(self._request(), "require-auth-toggle")

        self.assertIsNotNone(refusal)
        self.assertEqual(refusal.status_code, 401)
        self.assertEqual(refusal.data["error"], "step_up_required")

    @override_settings(STEP_UP=GATED)
    def test_a_grant_for_this_action_passes(self):
        self._enrol()
        grant = issue_grant(self.user.pk, "require-auth-toggle")

        refusal = self.view.check_step_up(
            self._request({"grant": grant}), "require-auth-toggle"
        )

        self.assertIsNone(refusal)

    @override_settings(STEP_UP=GATED)
    def test_a_grant_for_a_different_action_does_not(self):
        self._enrol()
        grant = issue_grant(self.user.pk, "disable")

        refusal = self.view.check_step_up(
            self._request({"grant": grant}), "require-auth-toggle"
        )

        self.assertEqual(refusal.status_code, 401)

    @override_settings(STEP_UP={"ACTIONS": set(), "MODE": "local"})
    def test_an_ungated_action_passes_untouched(self):
        self._enrol()

        self.assertIsNone(
            self.view.check_step_up(self._request(), "require-auth-toggle")
        )

    @override_settings(STEP_UP={**GATED, "NO_FACTOR_POLICY": "skip_gate"})
    def test_a_user_with_no_factor_is_waved_through_under_skip_gate(self):
        """The default, and the reason it needs a startup warning: the gate
        simply does not apply to anyone who has not enrolled."""
        self.assertIsNone(
            self.view.check_step_up(self._request(), "require-auth-toggle")
        )

    @override_settings(STEP_UP={**GATED, "NO_FACTOR_POLICY": "deny_prompt_enrol"})
    def test_a_user_with_no_factor_is_refused_under_deny(self):
        refusal = self.view.check_step_up(self._request(), "require-auth-toggle")

        self.assertEqual(refusal.status_code, 403)
        self.assertEqual(refusal.data["error"], "enrol_required")


FEDERATED = {"ACTIONS": {"require-auth-toggle"}, "MODE": "federated"}

FEDERATED_SERVER = {
    "kc": {
        "AUTHORIZATION_ENDPOINT": "https://idp.example/auth",
        "CLIENT_ID": "app",
        "REDIRECT_URI": "https://ona.example/stepup/callback",
        "SCOPE": "openid email",
        "STEP_UP": {"CLAIM": "acr", "SATISFIED_BY": ["gold"], "MAX_AGE": 0},
    }
}


@override_settings(
    STEP_UP={**FEDERATED, "NO_FACTOR_POLICY": "skip_gate"},
    OPENID_CONNECT_AUTH_SERVERS=FEDERATED_SERVER,
)
class TestFederatedGate(_GateHarness):
    """A federated deployment has no local device to look up.

    The IdP holds every factor, so every user looks factor-less from here.
    Reading that as "nothing to challenge" turns the gate into a no-op for the
    exact deployments it exists to protect.
    """

    def test_a_user_with_no_local_device_is_still_challenged(self):
        refusal = self.view.check_step_up(self._request(), "require-auth-toggle")

        self.assertIsNotNone(refusal)
        self.assertEqual(refusal.status_code, 401)
        self.assertEqual(refusal.data["dialect"], "oidc")

    def test_a_valid_grant_still_lets_the_action_through(self):
        """Challenging unconditionally would be the other failure: the gate
        must still honour a proof once one exists."""
        grant = issue_grant(self.user.pk, "require-auth-toggle")

        refusal = self.view.check_step_up(
            self._request({"grant": grant}), "require-auth-toggle"
        )

        self.assertIsNone(refusal)


@override_settings(
    STEP_UP=FEDERATED, OPENID_CONNECT_AUTH_SERVERS=FEDERATED_SERVER
)
class TestFederatedChallengeCannotBeBuilt(TestCase):
    """A gated request must answer even when the deployment is misconfigured.

    Raising here would surface as a 500 on an ordinary action rather than a
    challenge the client can report.
    """

    def setUp(self):
        self.user = get_user_model().objects.create(username="ana")

    @override_settings(OPENID_CONNECT_AUTH_SERVERS={})
    def test_no_configured_auth_server(self):
        body = build_challenge("require-auth-toggle", self.user)

        self.assertEqual(body["error"], "step_up_unavailable")

    def test_no_user_to_bind_the_state_to(self):
        body = build_challenge("require-auth-toggle", None)

        self.assertEqual(body["error"], "step_up_unavailable")

    def test_a_server_missing_its_endpoints(self):
        with patch(
            "onadata.libs.stepup.challenge.start_step_up",
            side_effect=ValueError("no AUTHORIZATION_ENDPOINT"),
        ):
            body = build_challenge("require-auth-toggle", self.user)

        self.assertEqual(body["error"], "step_up_unavailable")
