# -*- coding: utf-8 -*-
"""Tests for OnaData's half of a federated step-up.

The protocol half -- authorize URL, PKCE, claim matching, freshness -- is
ona-oidc's and is tested there. What is asserted here is what OnaData owns:
that the grant goes to the signed-in user, for the action they asked for, and
to nobody else. Driven through the viewset, so the ona-oidc callback mixin is
exercised rather than stubbed.
"""

import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from onadata.apps.api.viewsets.stepup_viewset import StepUpViewSet
from onadata.libs.stepup.federated import start_step_up
from oidc.stepup_grants import spend_grant

SERVERS = {
    "kc": {
        "AUTHORIZATION_ENDPOINT": "https://idp.example/auth",
        "CLIENT_ID": "app",
        "CLIENT_SECRET": "secret",
        "TOKEN_ENDPOINT": "https://idp.example/token",
        "JWKS_ENDPOINT": "https://idp.example/certs",
        "REDIRECT_URI": "https://ona.example/oidc/kc/callback",
        "SCOPE": "openid profile email",
        "USE_PKCE": True,
        "STEP_UP": {
            "CLAIM": "acr",
            "MATCH": "equals",
            "SATISFIED_BY": ["gold"],
            "MAX_AGE": 0,
            "MAX_AUTH_AGE_SECONDS": 300,
            "REQUIRE_AUTH_TIME": True,
            "SUBJECT_CLAIM": "email",
            "SUBJECT_FIELD": "email",
            "REDIRECT_URI": "https://ona.example/api/v1/stepup/callback",
        },
    }
}

SATISFYING = {"acr": "gold", "email": "ana@example.org"}


@override_settings(
    OPENID_CONNECT_AUTH_SERVERS=SERVERS,
    STEP_UP={"ACTIONS": {"require-auth-toggle"}, "MODE": "federated"},
)
class TestFederatedStepUp(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create(
            username="ana", email="ana@example.org"
        )
        _, self.state = start_step_up("kc", "require-auth-toggle", self.user)

    def _complete(self, claims, user=None, state=None):
        claims = {"auth_time": time.time(), **claims}
        with patch(
            "oidc.stepup.OpenIDClient.retrieve_tokens_using_auth_code",
            return_value={"id_token": "t"},
        ), patch(
            "oidc.stepup.OpenIDClient.verify_and_decode_id_token", return_value=claims
        ):
            request = type("R", (), {"user": user or self.user})()
            return StepUpViewSet().complete_step_up(
                request, code="c", state=state or self.state, auth_server="kc"
            )

    def test_a_satisfying_token_yields_a_grant_for_that_audience(self):
        grant, reason = self._complete(SATISFYING)

        self.assertIsNone(reason)
        self.assertTrue(spend_grant(self.user.pk, "require-auth-toggle", grant))

    def test_state_belonging_to_another_user_is_refused(self):
        other = get_user_model().objects.create(username="bo", email="bo@example.org")

        grant, reason = self._complete(SATISFYING, user=other)

        self.assertIsNone(grant)
        self.assertEqual(reason, "state_user_mismatch")

    def test_the_state_carries_the_audience_and_the_user(self):
        """The provider redirects back to a URL, not to the control the user
        clicked, so both have to survive the round trip -- and the callback
        refuses a state whose user is not the one redeeming it."""
        stashed = cache.get(f"oidc:step-up:{self.state}")["context"]

        self.assertEqual(stashed["audience"], "require-auth-toggle")
        self.assertEqual(stashed["user_pk"], self.user.pk)
