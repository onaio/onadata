# -*- coding: utf-8 -*-
"""
Tests for the federated step-up endpoints the SPA's popup drives.
"""

from unittest.mock import patch

from django.test.utils import override_settings

from oidc.stepup_grants import issue_grant

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.apps.api.viewsets.stepup_viewset import StepUpViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet

STEP_UP_FEDERATED = {
    "MODE": "oidc",
    "ACTIONS": ["require-auth-toggle"],
}


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
        """Nothing to redirect to: the code is proved against OnaData itself."""
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
        """A server missing its endpoints is the deployment's fault, not the
        user's, and must not surface as a traceback."""
        with patch(
            "onadata.apps.api.viewsets.stepup_viewset.start_step_up",
            side_effect=ValueError("no AUTHORIZATION_ENDPOINT"),
        ):
            response = self._start("require-auth-toggle")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["error"], "step_up_unavailable")

    @override_settings(STEP_UP=STEP_UP_FEDERATED, STEP_UP_POPUP_ORIGIN="https://app.test")
    def test_popup_posts_the_grant_only_to_this_deployments_spa(self):
        """The grant is a bearer credential; a ``*`` target hands it to anyone."""
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

    @override_settings(STEP_UP=STEP_UP_FEDERATED)
    def test_callback_rejects_a_request_with_no_code_or_state(self):
        response = self._callback(code="", state="")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "invalid_request")

    @override_settings(STEP_UP=STEP_UP_FEDERATED)
    def test_callback_keeps_the_reason_out_of_the_json_status(self):
        """A refused step-up is a 403, not a 200 the SPA might read as success."""
        with patch(
            "onadata.apps.api.viewsets.stepup_viewset.StepUpViewSet.complete_step_up",
            return_value=(None, "auth_time_stale"),
        ):
            response = self._callback(code="c", state="s")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"], "step_up_failed")


@override_settings(
    STEP_UP={
        "MODE": "local",
        "ACTIONS": ["privacy-consent"],
        "NO_FACTOR_POLICY": "skip_gate",
    },
    # Pinned rather than inherited: where the consent record lives is
    # deployment configuration, and reading the ambient value would make
    # these pass or fail on the environment.
    EU_CONSENT_METADATA_PATH=("client", "eu_citizen_consent"),
)
class TestPrivacyConsentGate(TestAbstractViewSet):
    """Changing the GDPR consent record needs the same proof as require_auth.

    It is a compliance statement about whose data this account collects, and
    it was previously changeable with nothing but a session.
    """

    def setUp(self):
        super().setUp()
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self.view = UserProfileViewSet.as_view({"patch": "partial_update"})

    def _patch(self, data):
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        return self.view(request, user=self.user.username)

    def _consent(self, collecting):
        # Matches EU_CONSENT_METADATA_PATH below. Nested, because a real
        # deployment namespaces its own metadata and the gate has to walk to
        # it rather than assume a flat key.
        return {
            "client": {
                "eu_citizen_consent": {
                    "is_collecting_eu_data": collecting,
                    "date": "2026-01-01T00:00:00Z",
                }
            }
        }

    def test_changing_consent_without_a_grant_is_challenged(self):
        response = self._patch({"metadata": self._consent(True)})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"], "step_up_required")
        self.assertEqual(response.data["audience"], "privacy-consent")

    def test_an_unrelated_metadata_edit_is_not_challenged(self):
        """The client PATCHes the whole blob; prompting for a city change
        would train users to approve challenges they did not ask for.

        Asserted on the gate's own input rather than through the endpoint,
        which continues into profile machinery this case is not about.
        """
        from onadata.apps.api.viewsets.user_profile_viewset import (
            _incoming_eu_consent,
        )

        self.assertIsNone(_incoming_eu_consent({"metadata": {"city": "Nairobi"}}))
        self.assertIsNone(_incoming_eu_consent({"require_auth": True}))

    def test_metadata_sent_as_a_json_string_is_still_gated(self):
        """Clients send it either way; reading only dicts would let the string
        form slip a consent change past the gate."""
        import json as _json

        from onadata.apps.api.viewsets.user_profile_viewset import (
            _incoming_eu_consent,
        )

        payload = {"metadata": _json.dumps(self._consent(True))}
        self.assertIsNotNone(_incoming_eu_consent(payload))

    def test_a_grant_for_another_action_does_not_spend_here(self):
        """Audience-scoped: proving a factor for the require_auth toggle must
        not silently carry a consent change through."""
        grant = issue_grant(self.user.pk, "require-auth-toggle")
        response = self._patch({"metadata": self._consent(True), "grant": grant})

        self.assertEqual(response.status_code, 401)


GATED_LOCAL = {
    "MODE": "local",
    "ACTIONS": ["regenerate-api-key", "change-email", "change-password"],
    "NO_FACTOR_POLICY": "skip_gate",
}


@override_settings(STEP_UP=GATED_LOCAL)
class TestAccountTakeoverGates(TestAbstractViewSet):
    """Two operations that were reachable with nothing but a session.

    Regenerating the token invalidates every integration holding the old one
    and mints a new long-lived credential; changing the email moves where
    password resets are delivered. Both are first moves in taking an account
    over.
    """

    def setUp(self):
        super().setUp()
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)

    def _regenerate(self, headers=None):
        view = ConnectViewSet.as_view({"get": "regenerate_auth_token"})
        return view(self.factory.get("/", **{**self.extra, **(headers or {})}))

    def _patch_email(self, data):
        view = UserProfileViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        return view(request, user=self.user.username)

    def test_regenerating_the_api_token_is_challenged(self):
        response = self._regenerate()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "regenerate-api-key")

    def test_a_grant_in_the_header_lets_the_regeneration_through(self):
        """A GET has no body, so the grant travels in a header rather than a
        query string -- which is written to logs, history and Referer."""
        grant = issue_grant(self.user.pk, "regenerate-api-key")

        response = self._regenerate({"HTTP_X_STEP_UP_GRANT": grant})

        self.assertNotEqual(response.status_code, 401)

    def test_a_grant_for_another_action_does_not_regenerate(self):
        grant = issue_grant(self.user.pk, "change-email")

        response = self._regenerate({"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 401)

    def test_changing_the_email_is_challenged(self):
        response = self._patch_email({"email": "somewhere.else@example.org"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "change-email")

    def test_changing_the_password_is_challenged(self):
        """It already demands the current password; the second factor is what
        a password alone cannot provide."""
        view = UserProfileViewSet.as_view({"post": "change_password"})
        request = self.factory.post(
            "/",
            data={"current_password": "x", "new_password": "y"},
            format="json",
            **self.extra,
        )

        response = view(request, user=self.user.username)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "change-password")

    def test_patching_the_same_email_is_not_challenged(self):
        """The client PATCHes the whole profile; prompting when nothing
        changed trains users to approve challenges they did not ask for."""
        response = self._patch_email({"email": self.user.email})

        self.assertNotEqual(response.status_code, 401)
