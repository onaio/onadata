# -*- coding: utf-8 -*-
"""
Tests for the federated step-up endpoints a client's popup drives.
"""

from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test.utils import override_settings
from django.urls import reverse

from registration.models import RegistrationProfile

from oidc.stepup_grants import issue_grant, spend_grant

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tools import get_organization_members
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet,
)
from onadata.apps.api.viewsets.stepup_viewset import StepUpViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.apps.api.viewsets.v2.organization_profile_viewset import (
    OrganizationProfileViewSet as OrganizationProfileViewSetV2,
)
from onadata.apps.logger.models.kms import KMSKey
from onadata.libs.permissions import ManagerRole, OwnerRole
from onadata.libs.utils.cache_tools import (
    CHANGE_PASSWORD_ATTEMPTS,
    LOCKOUT_CHANGE_PASSWORD_USER,
)

STEP_UP_FEDERATED = {
    "MODE": "federated",
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
    def test_popup_posts_the_grant_only_to_this_deployments_origin(self):
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
        """A 403, not a 200 a caller might read as success, with the same reason
        code the popup would receive."""
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

    It is a compliance statement about whose data this account collects, so a
    stolen session alone must not be able to change it.
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
        would train users to approve challenges they did not ask for."""
        response = self._patch({"metadata": {"city": "Nairobi"}})

        self.assertEqual(response.status_code, 200)

    def test_metadata_sent_as_a_json_string_is_still_gated(self):
        """Clients send it either way; reading only dicts would let the string
        form slip a consent change past the gate."""
        import json as _json

        response = self._patch({"metadata": _json.dumps(self._consent(True))})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "privacy-consent")

    def test_a_grant_for_another_action_does_not_spend_here(self):
        """Audience-scoped: proving a factor for the require_auth toggle must
        not silently carry a consent change through."""
        grant = issue_grant(self.user.pk, "require-auth-toggle")
        response = self._patch({"metadata": self._consent(True), "grant": grant})

        self.assertEqual(response.status_code, 401)

    def test_removing_the_consent_record_without_a_grant_is_challenged(self):
        """Dropping the record is a change too. The default PATCH replaces
        metadata wholesale, so a payload that omits the consent path clears the
        compliance statement. Gating only a differing value would let that
        through."""
        from onadata.apps.main.models import UserProfile

        profile = UserProfile.objects.get(user=self.user)
        profile.metadata = self._consent(True)
        profile.save()

        response = self._patch({"metadata": {}})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"], "step_up_required")
        self.assertEqual(response.data["audience"], "privacy-consent")
        # The refusal must leave the record intact.
        profile.refresh_from_db()
        self.assertEqual(profile.metadata, self._consent(True))

    def test_a_grant_lets_the_consent_record_be_removed(self):
        """The positive half: a privacy-consent grant lets the removal land, so
        the refusal above is the gate refusing, not the write failing for an
        unrelated reason."""
        from onadata.apps.main.models import UserProfile
        from onadata.libs.stepup.policy import eu_consent_record

        profile = UserProfile.objects.get(user=self.user)
        profile.metadata = self._consent(True)
        profile.save()
        grant = issue_grant(self.user.pk, "privacy-consent")

        response = self._patch({"metadata": {}, "grant": grant})

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertIsNone(eu_consent_record(profile.metadata))

    def test_a_put_with_overwrite_false_cannot_change_consent_ungated(self):
        """PUT ignores overwrite and writes metadata wholesale, so an
        overwrite=false in its body must not skip the gate the way it
        legitimately does for a PATCH merge."""
        from onadata.apps.main.models import UserProfile

        profile = UserProfile.objects.get(user=self.user)
        profile.metadata = self._consent(True)
        profile.save()
        view = UserProfileViewSet.as_view({"put": "update"})

        request = self.factory.put(
            "/",
            data={
                "username": self.user.username,
                "name": "Bob",
                "email": self.user.email,
                "metadata": self._consent(False),
                "overwrite": "false",
            },
            format="json",
            **self.extra,
        )
        response = view(request, user=self.user.username)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "privacy-consent")
        profile.refresh_from_db()
        self.assertEqual(profile.metadata, self._consent(True))


GATED_LOCAL = {
    "MODE": "local",
    "ACTIONS": [
        "regenerate-api-key",
        "regenerate-odk-token",
        "change-email",
        "change-password",
    ],
    "NO_FACTOR_POLICY": "skip_gate",
}


@override_settings(STEP_UP=GATED_LOCAL)
class TestAccountTakeoverGates(TestAbstractViewSet):
    """Two operations a stolen session alone must not be able to perform.

    Regenerating the token invalidates every integration holding the old one
    and mints a new long-lived credential; changing the email moves where
    password resets are delivered. Both are first moves in taking an account
    over.
    """

    def setUp(self):
        super().setUp()
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        RegistrationProfile.objects.create_profile(self.user)

    def _regenerate(self, headers=None):
        view = ConnectViewSet.as_view({"get": "regenerate_auth_token"})
        return view(self.factory.get("/", **{**self.extra, **(headers or {})}))

    def _regenerate_odk(self, headers=None):
        view = ConnectViewSet.as_view({"post": "odk_token"})
        return view(self.factory.post("/", **{**self.extra, **(headers or {})}))

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
        query string, which is written to logs, history and Referer."""
        grant = issue_grant(self.user.pk, "regenerate-api-key")

        response = self._regenerate({"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 201)

    def test_a_grant_for_another_action_does_not_regenerate(self):
        grant = issue_grant(self.user.pk, "change-email")

        response = self._regenerate({"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 401)

    @override_settings(
        CORS_ALLOW_ALL_ORIGINS=False,
        CORS_ALLOWED_ORIGINS=["https://app.example"],
    )
    def test_a_browser_on_another_origin_may_send_the_grant_header(self):
        """The header is the only way a grant reaches this GET, so a preflight
        that refuses it leaves the gate unsatisfiable from another origin."""
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
        response = self._regenerate_odk()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "regenerate-odk-token")

    def test_a_grant_lets_the_odk_token_regeneration_through(self):
        grant = issue_grant(self.user.pk, "regenerate-odk-token")

        response = self._regenerate_odk({"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 201)

    def test_an_api_token_grant_does_not_regenerate_the_odk_token(self):
        """Proving a factor to rotate one credential must not rotate the
        other."""
        grant = issue_grant(self.user.pk, "regenerate-api-key")

        response = self._regenerate_odk({"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "regenerate-odk-token")

    @override_settings(
        STEP_UP={
            **GATED_LOCAL,
            "ACTIONS": [*GATED_LOCAL["ACTIONS"], "require-auth-toggle"],
        }
    )
    def test_two_gated_changes_are_refused_without_spending_the_grant(self):
        """A request carries one grant, so it could never satisfy both."""
        grant = issue_grant(self.user.pk, "change-email")

        response = self._patch_email(
            {
                "email": "somewhere.else@example.org",
                "require_auth": not self.user.profile.require_auth,
                "password": self.login_password,
                "grant": grant,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "one_gated_change_per_request")
        self.assertEqual(
            response.data["audiences"], ["require-auth-toggle", "change-email"]
        )
        self.assertTrue(spend_grant(self.user.pk, "change-email", grant))

    def test_changing_the_email_is_challenged(self):
        response = self._patch_email({"email": "somewhere.else@example.org"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "change-email")

    @patch(
        "onadata.libs.serializers.user_profile_serializer."
        "send_verification_email.delay"
    )
    def test_a_grant_lets_the_email_change_through(self, _send_verification):
        grant = issue_grant(self.user.pk, "change-email")

        response = self._patch_email(
            {
                "email": "somewhere.else@example.org",
                "password": self.login_password,
                "grant": grant,
            }
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "somewhere.else@example.org")

    def test_an_email_change_without_the_password_keeps_the_grant(self):
        """The serializer demands the current password to change the email.
        Checked before the gate, so a request missing it keeps the grant."""
        grant = issue_grant(self.user.pk, "change-email")
        old_email = self.user.email

        response = self._patch_email(
            {"email": "somewhere.else@example.org", "grant": grant}
        )

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, old_email)
        self.assertTrue(spend_grant(self.user.pk, "change-email", grant))

    def test_an_email_change_with_a_wrong_password_keeps_the_grant(self):
        grant = issue_grant(self.user.pk, "change-email")
        old_email = self.user.email

        response = self._patch_email(
            {
                "email": "somewhere.else@example.org",
                "password": "not-my-password",
                "grant": grant,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, old_email)
        self.assertTrue(spend_grant(self.user.pk, "change-email", grant))

    def test_changing_the_password_is_challenged(self):
        """It already demands the current password; the second factor is what
        a password alone cannot provide."""
        new_password = "Tr0ub4dor-and-3-horses"
        view = UserProfileViewSet.as_view({"post": "change_password"})
        request = self.factory.post(
            "/",
            data={
                "current_password": self.login_password,
                "new_password": new_password,
            },
            format="json",
            **self.extra,
        )

        response = view(request, user=self.user.username)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "change-password")
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password(new_password))

    def test_a_mistyped_current_password_keeps_the_grant(self):
        """Validated before the gate, as the settings page is, so the retry
        does not need a second factor proved again."""
        new_password = "Tr0ub4dor-and-3-horses"
        grant = issue_grant(self.user.pk, "change-password")
        view = UserProfileViewSet.as_view({"post": "change_password"})
        # The failed attempt is counted in the cache, which the test database
        # rollback does not undo.
        username = self.user.username
        self.addCleanup(cache.delete, f"{CHANGE_PASSWORD_ATTEMPTS}{username}")
        self.addCleanup(cache.delete, f"{LOCKOUT_CHANGE_PASSWORD_USER}{username}")

        def change(current_password):
            request = self.factory.post(
                "/",
                data={
                    "current_password": current_password,
                    "new_password": new_password,
                    "grant": grant,
                },
                format="json",
                **self.extra,
            )
            return view(request, user=self.user.username)

        self.assertEqual(change("not-my-password").status_code, 400)
        self.assertEqual(change(self.login_password).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_a_grant_lets_the_password_change_through(self):
        new_password = "Tr0ub4dor-and-3-horses"
        grant = issue_grant(self.user.pk, "change-password")
        view = UserProfileViewSet.as_view({"post": "change_password"})
        request = self.factory.post(
            "/",
            data={
                "current_password": self.login_password,
                "new_password": new_password,
                "grant": grant,
            },
            format="json",
            **self.extra,
        )

        response = view(request, user=self.user.username)

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    @patch(
        "onadata.libs.serializers.user_profile_serializer."
        "send_verification_email.delay"
    )
    def test_patching_the_same_email_is_not_challenged(self, _send_verification):
        """The client PATCHes the whole profile; prompting when nothing
        changed trains users to approve challenges they did not ask for.

        Carries the password the serializer demands alongside an email, so the
        write succeeds rather than failing for a reason unrelated to the gate.
        """
        response = self._patch_email(
            {"email": self.user.email, "password": self.login_password}
        )

        self.assertEqual(response.status_code, 200)


@override_settings(
    STEP_UP={
        "MODE": "local",
        "ACTIONS": ["require-auth-toggle"],
        "NO_FACTOR_POLICY": "skip_gate",
    }
)
class TestOrganisationRequireAuthGate(TestAbstractViewSet):
    """An organisation's profile is a UserProfile, so its require_auth is the
    same column the personal profile gates."""

    def setUp(self):
        super().setUp()
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self._org_create()

    def _patch_org(self, data, headers=None):
        view = OrganizationProfileViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data=data, format="json", **{**self.extra, **(headers or {})}
        )
        return view(request, user="denoinc")

    def _require_auth(self):
        return OrganizationProfile.objects.get(user__username="denoinc").require_auth

    def test_toggling_require_auth_is_challenged(self):
        self.assertFalse(self._require_auth())

        response = self._patch_org({"require_auth": True})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "require-auth-toggle")
        self.assertFalse(self._require_auth())

    def test_a_grant_lets_the_toggle_through(self):
        grant = issue_grant(self.user.pk, "require-auth-toggle")

        response = self._patch_org(
            {"require_auth": True}, {"HTTP_X_STEP_UP_GRANT": grant}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._require_auth())

    def test_other_changes_are_not_challenged(self):
        response = self._patch_org({"name": "Dennis Inc", "require_auth": False})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            OrganizationProfile.objects.get(user__username="denoinc").name,
            "Dennis Inc",
        )


@override_settings(
    STEP_UP={
        "MODE": "local",
        "ACTIONS": ["grant-org-admin"],
        "NO_FACTOR_POLICY": "skip_gate",
    }
)
class TestOrganisationAdminRoleGate(TestAbstractViewSet):
    """An owner or manager can change every gated setting of the
    organisation with their own factor, so a stolen session must not be able
    to appoint one."""

    def setUp(self):
        super().setUp()
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self._org_create()
        self.alice = self._create_user("alice", "alice", create_profile=True)
        self.assertNotEqual(self.alice, self.user)
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.organization))

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _member_request(
        self,
        method,
        role,
        headers=None,
        username="alice",
        viewset=OrganizationProfileViewSet,
    ):
        view = viewset.as_view({method: "members"})
        request = getattr(self.factory, method)(
            "/",
            data={"username": username, "role": role},
            format="json",
            **{**self.extra, **(headers or {})},
        )
        return view(request, user="denoinc")

    def _add_member(self, role, headers=None):
        return self._member_request("post", role, headers)

    def _make_alice(self, role=None):
        self._add_user_to_organization(self.organization, self.alice, role)
        self.assertIn(self.alice, get_organization_members(self.organization))

    def test_appointing_an_owner_is_challenged(self):
        response = self._add_member("owner")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "grant-org-admin")
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))

    def test_a_grant_lets_the_owner_through(self):
        grant = issue_grant(self.user.pk, "grant-org-admin")

        response = self._add_member("owner", {"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 201)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.organization))

    def test_other_roles_are_not_challenged(self):
        response = self._add_member("editor")

        self.assertEqual(response.status_code, 201)
        self.assertIn(self.alice, get_organization_members(self.organization))
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))

    def test_appointing_a_manager_through_v2_is_challenged(self):
        response = self._member_request(
            "post", "manager", viewset=OrganizationProfileViewSetV2
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "grant-org-admin")
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.organization))

    def test_re_appointing_an_owner_is_not_challenged(self):
        self._make_alice("owner")
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.organization))

        response = self._add_member("owner")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.organization))

    def test_demoting_an_owner_to_manager_is_not_challenged(self):
        self._make_alice("owner")
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.organization))

        response = self._member_request("put", "manager")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.organization))
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))

    def test_an_unknown_username_keeps_the_grant(self):
        """The username is validated first, so a typo does not spend it."""
        grant = issue_grant(self.user.pk, "grant-org-admin")

        response = self._member_request(
            "post", "owner", {"HTTP_X_STEP_UP_GRANT": grant}, username="nobody"
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(spend_grant(self.user.pk, "grant-org-admin", grant))

    def test_promoting_a_member_to_owner_through_v1_put_is_challenged(self):
        self._make_alice()

        response = self._member_request("put", "owner")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "grant-org-admin")
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))

    def test_appointing_a_manager_through_v1_is_challenged(self):
        response = self._add_member("manager")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "grant-org-admin")
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.organization))

    def test_a_grant_lets_the_owner_through_v2(self):
        grant = issue_grant(self.user.pk, "grant-org-admin")

        response = self._member_request(
            "post",
            "owner",
            {"HTTP_X_STEP_UP_GRANT": grant},
            viewset=OrganizationProfileViewSetV2,
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.organization))

    def test_promoting_a_member_to_manager_through_v2_patch_is_challenged(self):
        self._make_alice()

        response = self._member_request(
            "patch", "manager", viewset=OrganizationProfileViewSetV2
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "grant-org-admin")
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.organization))


@override_settings(
    STEP_UP={
        "MODE": "local",
        "ACTIONS": ["rotate-org-key"],
        "NO_FACTOR_POLICY": "skip_gate",
    }
)
@patch("onadata.libs.serializers.organization_serializer.rotate_key")
class TestOrganisationKeyRotationGate(TestAbstractViewSet):
    """Rotating the organisation's encryption key makes every device fetch
    the re-keyed forms, so a stolen session alone must not trigger it."""

    def setUp(self):
        super().setUp()
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self._org_create()
        self.content_type = ContentType.objects.get_for_model(OrganizationProfile)
        self.kms_key = self._key("fake-key-id")

    def _key(self, key_id):
        return KMSKey.objects.create(
            key_id=key_id,
            description="Key-2025-04-25",
            public_key="fake-pub-key",
            content_type=self.content_type,
            object_id=self.organization.pk,
            provider=KMSKey.KMSProvider.AWS,
        )

    def _rotate(self, key_id, headers=None):
        view = OrganizationProfileViewSet.as_view({"post": "rotate_key"})
        request = self.factory.post(
            "/", data={"id": key_id}, **{**self.extra, **(headers or {})}
        )
        return view(request, user="denoinc")

    def test_rotating_the_key_is_challenged(self, mock_rotate_key):
        response = self._rotate(self.kms_key.id)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "rotate-org-key")
        mock_rotate_key.assert_not_called()

    def test_a_grant_lets_the_rotation_through(self, mock_rotate_key):
        mock_rotate_key.return_value = self._key("new-key")
        grant = issue_grant(self.user.pk, "rotate-org-key")

        response = self._rotate(self.kms_key.id, {"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 200)
        mock_rotate_key.assert_called_once()

    def test_an_invalid_key_keeps_the_grant(self, mock_rotate_key):
        """Validation comes first, so a mistyped key id does not spend it."""
        grant = issue_grant(self.user.pk, "rotate-org-key")

        response = self._rotate(0, {"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 400)
        self.assertTrue(spend_grant(self.user.pk, "rotate-org-key", grant))
        mock_rotate_key.assert_not_called()
