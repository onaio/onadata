# -*- coding: utf-8 -*-
"""
Tests for the federated step-up endpoints a client's popup drives.
"""

import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from oidc.stepup_grants import spend_grant

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.stepup_viewset import StepUpViewSet
from onadata.libs.stepup.federated import start_step_up

STEP_UP_FEDERATED = {
    "MODE": "federated",
    "ACTIONS": ["require-auth-toggle"],
}

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


class TestStepUpViewSet(TestAbstractViewSet):
    """Where the popup starts, and what comes back to it."""

    def _start(self, audience):
        view = StepUpViewSet.as_view({"get": "start"})
        return view(self.factory.get("/", {"audience": audience}, **self.extra))

    def _callback(self, accept=None, **params):
        view = StepUpViewSet.as_view({"get": "callback"})
        extra = dict(self.extra)
        if accept:
            extra["HTTP_ACCEPT"] = accept
        return view(self.factory.get("/", params, **extra))

    @override_settings(STEP_UP={"MODE": "local", "ACTIONS": ["a"]})
    def test_start_refuses_when_the_factor_is_local(self):
        """Local mode checks the code against OnaData, so there is nothing to
        redirect to."""
        response = self._start("a")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "not_federated")

    @override_settings(STEP_UP=STEP_UP_FEDERATED)
    def test_start_refuses_an_audience_that_is_not_gated(self):
        """Otherwise any caller could mint a grant for an ungated action."""
        response = self._start("something-else")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "not_gated")

    @override_settings(STEP_UP=STEP_UP_FEDERATED)
    def test_start_returns_the_authorization_url(self):
        # Patched where the viewset looks it up, not where it is defined.
        with patch(
            "onadata.apps.api.viewsets.stepup_viewset.start_step_up",
            return_value=("https://idp.test/authorize?acr_values=mfa", "state-1"),
        ):
            response = self._start("require-auth-toggle")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["authorizationUrl"],
            "https://idp.test/authorize?acr_values=mfa",
        )

    @override_settings(STEP_UP=STEP_UP_FEDERATED)
    def test_start_reports_a_deployment_with_nowhere_to_send_the_user(self):
        """A server without its endpoints is a deployment fault, not the
        user's. It must not end in a traceback."""
        with patch(
            "onadata.apps.api.viewsets.stepup_viewset.start_step_up",
            side_effect=ValueError("no AUTHORIZATION_ENDPOINT"),
        ):
            response = self._start("require-auth-toggle")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["error"], "step_up_unavailable")

    @override_settings(
        STEP_UP=STEP_UP_FEDERATED, STEP_UP_POPUP_ORIGIN="https://app.test"
    )
    def test_popup_posts_the_grant_only_to_this_deployments_origin(self):
        """The grant is a bearer credential. A ``*`` target hands it to anyone."""
        with patch(
            "onadata.apps.api.viewsets.stepup_viewset.StepUpViewSet.complete_step_up",
            return_value=("grant-42", None),
        ):
            response = self._callback(accept="text/html", code="c", state="s")

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('"https://app.test"', body)
        self.assertNotIn('"*"', body)
        self.assertIn("grant-42", body)

    @override_settings(
        STEP_UP=STEP_UP_FEDERATED, STEP_UP_POPUP_ORIGIN="https://app.test"
    )
    def test_a_cancelled_prompt_still_reports_back_to_the_opener(self):
        """The provider returns ``error`` and no code. A bare 400 would leave
        the opener waiting."""
        response = self._callback(accept="text/html", error="access_denied", state="s")

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("postMessage", body)
        self.assertIn('"error": "provider_error"', body)

    @override_settings(STEP_UP=STEP_UP_FEDERATED)
    def test_the_callback_accepts_the_django_session(self):
        """The popup returning from the provider carries cookies, not a
        token."""
        self.client.force_login(self.user)
        with patch(
            "onadata.apps.api.viewsets.stepup_viewset.StepUpViewSet.complete_step_up",
            return_value=("grant-7", None),
        ):
            response = self.client.get(
                reverse("stepup-callback"), {"code": "c", "state": "s"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["grant"], "grant-7")

    @override_settings(STEP_UP=STEP_UP_FEDERATED)
    def test_callback_rejects_a_request_with_no_code_or_state(self):
        response = self._callback(code="", state="")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "invalid_request")

    @override_settings(STEP_UP=STEP_UP_FEDERATED)
    def test_a_refused_step_up_is_a_403_carrying_its_reason(self):
        """A 403, not a 200 a caller might read as success. It carries the
        reason code the popup would receive."""
        with patch(
            "onadata.apps.api.viewsets.stepup_viewset.StepUpViewSet.complete_step_up",
            return_value=(None, "auth_time_stale"),
        ):
            response = self._callback(code="c", state="s")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"], "step_up_failed")
        self.assertEqual(response.data["reason"], "auth_time_stale")

    @override_settings(STEP_UP=STEP_UP_FEDERATED)
    def test_a_completed_step_up_returns_the_grant(self):
        with patch(
            "onadata.apps.api.viewsets.stepup_viewset.StepUpViewSet.complete_step_up",
            return_value=("grant-42", None),
        ):
            response = self._callback(code="c", state="s")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"grant": "grant-42"})
        self.assertEqual(response["Cache-Control"], "no-store")


@override_settings(
    OPENID_CONNECT_AUTH_SERVERS=SERVERS,
    STEP_UP={"ACTIONS": {"require-auth-toggle"}, "MODE": "federated"},
)
class TestFederatedStepUp(TestCase):
    """OnaData's half of a federated step-up.

    ona-oidc owns and tests the protocol half. That covers the authorize URL,
    PKCE, claim matching and freshness. These tests cover what OnaData owns.
    The grant goes to the signed-in user, for the action they asked for, and
    to nobody else.
    """

    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create(
            username="ana", email="ana@example.org"
        )
        url, self.state = start_step_up("kc", "require-auth-toggle", self.user)
        self.nonce = parse_qs(urlparse(url).query)["nonce"][0]

    def _complete(self, claims, user=None, state=None):
        claims = {"auth_time": time.time(), "nonce": self.nonce, **claims}
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
