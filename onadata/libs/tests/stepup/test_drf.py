# -*- coding: utf-8 -*-
"""Tests for the DRF gate."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from django_otp.plugins.otp_totp.models import TOTPDevice
from oidc.stepup_grants import issue_grant
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from onadata.libs.stepup.drf import RequiresStepUp
from onadata.libs.tests.stepup.test_challenge import (
    FEDERATED,
    FEDERATED_SERVER,
    GATED,
)


class _View(RequiresStepUp):
    pass


class _GateHarness(TestCase):
    """Requests carry an explicit parser.

    The gate reads ``request.data``, and a request built without parsers
    raises UnsupportedMediaType instead of returning the grant.
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
        """skip_gate is the default. The gate does not apply to a user who
        has not enrolled."""
        self.assertIsNone(
            self.view.check_step_up(self._request(), "require-auth-toggle")
        )

    @override_settings(STEP_UP={**GATED, "NO_FACTOR_POLICY": "deny_prompt_enrol"})
    def test_a_user_with_no_factor_is_refused_under_deny(self):
        refusal = self.view.check_step_up(self._request(), "require-auth-toggle")

        self.assertEqual(refusal.status_code, 403)
        self.assertEqual(refusal.data["error"], "enrol_required")

    @override_settings(STEP_UP={**GATED, "NO_FACTOR_POLICY": "deny_prompt_enroll"})
    def test_a_misspelt_policy_refuses_rather_than_skips(self):
        refusal = self.view.check_step_up(self._request(), "require-auth-toggle")

        self.assertEqual(refusal.status_code, 403)
        self.assertEqual(refusal.data["error"], "enrol_required")


@override_settings(
    STEP_UP={**FEDERATED, "NO_FACTOR_POLICY": "skip_gate"},
    OPENID_CONNECT_AUTH_SERVERS=FEDERATED_SERVER,
)
class TestFederatedGate(_GateHarness):
    """A federated deployment has no local device to look up, so the gate
    challenges every user."""

    def test_a_user_with_no_local_device_is_still_challenged(self):
        refusal = self.view.check_step_up(self._request(), "require-auth-toggle")

        self.assertIsNotNone(refusal)
        self.assertEqual(refusal.status_code, 401)
        self.assertEqual(refusal.data["dialect"], "oidc")
        self.assertIn("authorizationUrl", refusal.data)

    def test_a_valid_grant_still_lets_the_action_through(self):
        """The gate still honours a valid grant in federated mode."""
        grant = issue_grant(self.user.pk, "require-auth-toggle")

        refusal = self.view.check_step_up(
            self._request({"grant": grant}), "require-auth-toggle"
        )

        self.assertIsNone(refusal)


@override_settings(STEP_UP=FEDERATED, OPENID_CONNECT_AUTH_SERVERS={})
class TestUnavailableStepUp(_GateHarness):
    """A deployment with nowhere to send the user cannot be satisfied by the
    caller, so the gate answers as the start endpoint does."""

    def test_a_gate_that_cannot_build_a_challenge_answers_503(self):
        refusal = self.view.check_step_up(self._request(), "require-auth-toggle")

        self.assertIsNotNone(refusal)
        self.assertEqual(refusal.status_code, 503)
        self.assertEqual(refusal.data, {"error": "step_up_unavailable"})
