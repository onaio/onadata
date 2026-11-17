# -*- coding: utf-8 -*-
"""
Tests for the step-up gates on regenerating the API and ODK tokens.
"""

from django.test.utils import override_settings
from django.urls import reverse

from oidc.stepup_grants import issue_grant
from registration.models import RegistrationProfile
from rest_framework.authtoken.models import Token

from onadata.apps.api.models.odk_token import ODKToken
from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    StepUpGateTestCase,
    gating,
)
from onadata.apps.api.tests.viewsets.test_stepup_user_profile_gates import (
    ACCOUNT_ACTIONS,
)
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet


@gating(*ACCOUNT_ACTIONS)
class TestTokenRegenerationGates(StepUpGateTestCase):
    """Regenerating a token breaks every integration that holds the old one
    and mints a new long-lived credential. A stolen session alone must not be
    able to do it.
    """

    def setUp(self):
        super().setUp()
        RegistrationProfile.objects.create_profile(self.user)

    def _regenerate(self, headers=None):
        view = ConnectViewSet.as_view({"get": "regenerate_auth_token"})
        return view(self.factory.get("/", **{**self.extra, **(headers or {})}))

    def _regenerate_odk(self, headers=None):
        view = ConnectViewSet.as_view({"post": "odk_token"})
        return view(self.factory.post("/", **{**self.extra, **(headers or {})}))

    def _api_token(self):
        return Token.objects.get(user=self.user).key

    def _active_odk_tokens(self):
        return list(
            ODKToken.objects.filter(user=self.user, status=ODKToken.ACTIVE)
            .order_by("pk")
            .values_list("pk", flat=True)
        )

    def test_regenerating_the_api_token_is_challenged(self):
        old_token = self._api_token()

        response = self._regenerate()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "regenerate-api-key")
        self.assertEqual(self._api_token(), old_token)

    def test_a_grant_in_the_header_lets_the_regeneration_through(self):
        """A GET has no body, so the grant travels in a header. A query string
        would be written to logs, browser history and the Referer header."""
        grant = issue_grant(self.user.pk, "regenerate-api-key")
        old_token = self._api_token()

        response = self._regenerate({"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(self._api_token(), old_token)
        self.assertEqual(response.data, self._api_token())

    @override_settings(
        CORS_ALLOW_ALL_ORIGINS=False,
        CORS_ALLOWED_ORIGINS=["https://app.example"],
    )
    def test_a_browser_on_another_origin_may_send_the_grant_header(self):
        """The header is the only way a grant reaches this GET. A preflight
        that refuses it would make the gate impossible to pass from another
        origin."""
        response = self.client.options(
            reverse("connect-regenerate-auth-token"),
            HTTP_ORIGIN="https://app.example",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="x-step-up-grant",
        )

        self.assertEqual(response["access-control-allow-origin"], "https://app.example")
        self.assertIn("x-step-up-grant", response["access-control-allow-headers"])

    def test_regenerating_the_odk_token_is_challenged(self):
        """Rotating the ODK token invalidates a live ODK Collect credential,
        so it is gated like the API token."""
        old_token = ODKToken.objects.create(user=self.user)

        response = self._regenerate_odk()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "regenerate-odk-token")
        self.assertEqual(self._active_odk_tokens(), [old_token.pk])

    def test_a_grant_lets_the_odk_token_regeneration_through(self):
        old_token = ODKToken.objects.create(user=self.user)
        grant = issue_grant(self.user.pk, "regenerate-odk-token")

        response = self._regenerate_odk({"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 201)
        active = self._active_odk_tokens()
        self.assertEqual(len(active), 1)
        self.assertNotEqual(active, [old_token.pk])
