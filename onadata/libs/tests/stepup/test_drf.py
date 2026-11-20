# -*- coding: utf-8 -*-
"""Tests for the DRF gate."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
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

    def _request(self, data=None, **extra):
        request = Request(
            self.factory.post("/", data or {}, format="json", **extra),
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


@override_settings(STEP_UP=GATED)
class TestGateInputs(_GateHarness):
    """The default skip_gate policy lets a user with no factor through, so a
    refusal here comes from the input, not the policy."""

    def test_an_anonymous_request_is_challenged(self):
        request = self._request()
        request.user = AnonymousUser()

        refusal = self.view.check_step_up(request, "require-auth-toggle")

        self.assertEqual(refusal.status_code, 401)
        self.assertEqual(refusal.data["error"], "step_up_required")

    def test_a_malformed_grant_is_treated_as_none(self):
        """A value that cannot be a grant never reaches the cache, where it
        would be an invalid key."""
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        malformed = "not a grant/" + "x" * 300

        with patch("onadata.libs.stepup.gate.spend_grant", return_value=False) as spend:
            refusal = self.view.check_step_up(
                self._request(HTTP_X_STEP_UP_GRANT=malformed), "require-auth-toggle"
            )

        self.assertEqual(refusal.status_code, 401)
        spend.assert_called_once_with(self.user.pk, "require-auth-toggle", "")


@override_settings(STEP_UP=GATED)
class TestGateAuditLog(_GateHarness):
    """Gate decisions reach the security audit log, without the grant."""

    def setUp(self):
        super().setUp()
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)

    def _check(self, request):
        with self.assertLogs("audit_logger", level="DEBUG") as captured:
            refusal = self.view.check_step_up(request, "require-auth-toggle")
        return refusal, captured.records

    def _assert_recorded(self, records, action, grant):
        matching = [r for r in records if getattr(r, "formhub_action", None) == action]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].audit, {"audience": "require-auth-toggle"})
        for record in records:
            self.assertNotIn(grant, record.getMessage())
            self.assertNotIn(grant, str(record.audit))

    def test_a_spent_grant_is_recorded(self):
        grant = issue_grant(self.user.pk, "require-auth-toggle")

        refusal, records = self._check(self._request({"grant": grant}))

        self.assertIsNone(refusal)
        self._assert_recorded(records, "step-up-grant-spent", grant)

    def test_a_grant_for_another_action_is_recorded_as_rejected(self):
        grant = issue_grant(self.user.pk, "disable")

        refusal, records = self._check(self._request({"grant": grant}))

        self.assertEqual(refusal.status_code, 401)
        self._assert_recorded(records, "step-up-grant-rejected", grant)

    def test_a_replayed_grant_is_recorded_as_rejected(self):
        grant = issue_grant(self.user.pk, "require-auth-toggle")
        self.assertIsNone(
            self.view.check_step_up(
                self._request({"grant": grant}), "require-auth-toggle"
            )
        )

        refusal, records = self._check(self._request({"grant": grant}))

        self.assertEqual(refusal.status_code, 401)
        self._assert_recorded(records, "step-up-grant-rejected", grant)

    @override_settings(STEP_UP={**GATED, "NO_FACTOR_POLICY": "deny_prompt_enrol"})
    def test_an_enrol_required_refusal_is_recorded(self):
        TOTPDevice.objects.filter(user=self.user).delete()

        refusal, records = self._check(self._request())

        self.assertEqual(refusal.data["error"], "enrol_required")
        actions = [getattr(r, "formhub_action", None) for r in records]
        self.assertIn("step-up-enrol-required", actions)

    def test_a_request_without_a_grant_records_no_rejection(self):
        with self.assertNoLogs("audit_logger", level="DEBUG"):
            refusal = self.view.check_step_up(self._request(), "require-auth-toggle")

        self.assertEqual(refusal.status_code, 401)
