# -*- coding: utf-8 -*-
"""Tests for the challenge body."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from onadata.libs.stepup.challenge import build_challenge

GATED = {"ACTIONS": {"require-auth-toggle"}, "MODE": "local"}

FEDERATED = {"ACTIONS": {"require-auth-toggle"}, "MODE": "federated"}

FEDERATED_SERVER = {
    "kc": {
        "AUTHORIZATION_ENDPOINT": "https://idp.example/auth",
        "CLIENT_ID": "app",
        "SCOPE": "openid email",
        "STEP_UP": {
            "CLAIM": "acr",
            "SATISFIED_BY": ["gold"],
            "MAX_AGE": 0,
            "REDIRECT_URI": "https://ona.example/api/v1/stepup/callback",
        },
    }
}


class TestChallenge(TestCase):
    @override_settings(STEP_UP=GATED)
    def test_local_mode_asks_for_a_code(self):
        body = build_challenge("require-auth-toggle")

        self.assertEqual(body["error"], "step_up_required")
        self.assertEqual(body["dialect"], "local-totp")
        # A client echoes the audience to /totp/verify. Without it, the grant
        # it gets back cannot be spent on this action.
        self.assertEqual(body["audience"], "require-auth-toggle")


@override_settings(STEP_UP=FEDERATED, OPENID_CONNECT_AUTH_SERVERS=FEDERATED_SERVER)
class TestFederatedChallengeCannotBeBuilt(TestCase):
    """A gated request must answer even when the deployment is misconfigured.

    Raising here would return a 500 on an ordinary action instead of a
    challenge a client can report.
    """

    def setUp(self):
        self.user = get_user_model().objects.create(username="ana")

    def test_no_user_to_bind_the_state_to(self):
        body = build_challenge("require-auth-toggle", None)

        self.assertEqual(body["error"], "step_up_unavailable")

    def test_an_anonymous_user_to_bind_the_state_to(self):
        body = build_challenge("require-auth-toggle", AnonymousUser())

        self.assertEqual(body["error"], "step_up_unavailable")

    def test_a_server_with_a_malformed_config(self):
        for error in (ImproperlyConfigured("no CLIENT_ID"), TypeError("bad")):
            with self.subTest(error=type(error).__name__), patch(
                "onadata.libs.stepup.challenge.start_step_up", side_effect=error
            ):
                body = build_challenge("require-auth-toggle", self.user)

                self.assertEqual(body["error"], "step_up_unavailable")

    def test_a_server_missing_its_endpoints(self):
        with patch(
            "onadata.libs.stepup.challenge.start_step_up",
            side_effect=ValueError("no AUTHORIZATION_ENDPOINT"),
        ):
            body = build_challenge("require-auth-toggle", self.user)

        self.assertEqual(body["error"], "step_up_unavailable")
