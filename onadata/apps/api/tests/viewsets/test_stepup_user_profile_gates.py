# -*- coding: utf-8 -*-
"""
Tests for the step-up gates on the user profile endpoints that change the
consent record, the email or the password.
"""

import json
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings

from oidc.stepup_grants import issue_grant, spend_grant
from registration.models import RegistrationProfile

from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    StepUpGateTestCase,
    gating,
)
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.apps.main.models import UserProfile
from onadata.libs.stepup.policy import eu_consent_record
from onadata.libs.utils.cache_tools import (
    CHANGE_PASSWORD_ATTEMPTS,
    LOCKOUT_CHANGE_PASSWORD_USER,
)

#: The account actions a deployment gates together.
ACCOUNT_ACTIONS = (
    "regenerate-api-key",
    "regenerate-odk-token",
    "change-email",
    "change-password",
)


@gating(
    "privacy-consent",
    # Pin the path. Where the consent record lives is deployment
    # configuration, and the ambient value would make these tests depend on
    # the environment.
    EU_CONSENT_METADATA_PATH=("client", "eu_citizen_consent"),
)
class TestPrivacyConsentGate(StepUpGateTestCase):
    """Changing the GDPR consent record needs the same proof as require_auth.

    The record is a compliance statement about whose data this account
    collects. A stolen session alone must not be able to change it.
    """

    def setUp(self):
        super().setUp()
        self.view = UserProfileViewSet.as_view({"patch": "partial_update"})

    def _patch(self, data):
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        return self.view(request, user=self.user.username)

    def _consent(self, collecting):
        # Matches EU_CONSENT_METADATA_PATH above. The path is nested because
        # a deployment namespaces its own metadata, so the gate must not
        # assume a flat key.
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
        """A client may PATCH the whole blob. Prompting for a city change
        would train users to approve challenges they did not ask for."""
        self.assertEqual(
            self._patch({"metadata": self._consent(True)}).status_code, 401
        )

        response = self._patch({"metadata": {"city": "Nairobi"}})

        self.assertEqual(response.status_code, 200)

    def test_metadata_sent_as_a_json_string_is_still_gated(self):
        """Clients send metadata as a dict or a JSON string. Reading only
        dicts would let a consent change through as a string."""
        response = self._patch({"metadata": json.dumps(self._consent(True))})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "privacy-consent")

    def test_removing_the_consent_record_without_a_grant_is_challenged(self):
        """Dropping the record is a change too. The default PATCH replaces
        metadata wholesale, so a payload without the consent path clears the
        record. Gating only a differing value would let that through."""
        profile = UserProfile.objects.get(user=self.user)
        profile.metadata = self._consent(True)
        profile.save()

        response = self._patch({"metadata": {}})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"], "step_up_required")
        self.assertEqual(response.data["audience"], "privacy-consent")
        profile.refresh_from_db()
        self.assertEqual(profile.metadata, self._consent(True))

    def test_a_grant_lets_the_consent_record_be_removed(self):
        profile = UserProfile.objects.get(user=self.user)
        profile.metadata = self._consent(True)
        profile.save()
        grant = issue_grant(self.user.pk, "privacy-consent")

        response = self._patch({"metadata": {}, "grant": grant})

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertIsNone(eu_consent_record(profile.metadata))

    def test_a_put_with_overwrite_false_cannot_change_consent_ungated(self):
        """PUT ignores overwrite and writes metadata wholesale. An
        overwrite=false in its body must not skip the gate as it does for a
        PATCH merge."""
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
                "password": self.login_password,
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


@gating(*ACCOUNT_ACTIONS)
class TestEmailAndPasswordGates(StepUpGateTestCase):
    """Changing the email moves where password resets are delivered.
    Changing the password replaces the credential itself. A stolen session
    alone must not be able to do either.
    """

    def setUp(self):
        super().setUp()
        RegistrationProfile.objects.create_profile(self.user)

    def _patch_email(self, data):
        view = UserProfileViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        return view(request, user=self.user.username)

    @gating(*ACCOUNT_ACTIONS, "require-auth-toggle")
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
        """The request carries the password the serializer requires, so only
        the gate can refuse it."""
        response = self._patch_email(
            {"email": "somewhere.else@example.org", "password": self.login_password}
        )

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
        """The serializer requires the current password to change the email.
        It checks this before the gate, so a request without it keeps the
        grant."""
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
        # The wrong password is counted in the cache, which the test database
        # rollback does not undo.
        self.addCleanup(cache.clear)
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

    @override_settings(MAX_LOGIN_ATTEMPTS=3)
    def test_repeated_wrong_passwords_lock_out_the_email_change(self):
        """The password check spends the login form's allowance, so it is
        no way to guess the password around the lockout."""
        # The counter lives in the cache, which the test runner does not roll
        # back.
        cache.clear()
        self.addCleanup(cache.clear)
        new_email = {"email": "somewhere.else@example.org"}
        challenged = self._patch_email({**new_email, "password": self.login_password})
        self.assertEqual(challenged.data["audience"], "change-email")

        with patch(
            "onadata.libs.authentication.send_account_lockout_email.apply_async"
        ):
            first = self._patch_email({**new_email, "password": "not-my-password"})
            for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):
                self._patch_email({**new_email, "password": "not-my-password"})

            refused = self._patch_email({**new_email, "password": self.login_password})

        self.assertEqual(first.status_code, 400)
        self.assertEqual(first.data["non_field_errors"], ["Invalid password"])
        self.assertEqual(refused.status_code, 403, refused.data)
        self.assertEqual(refused.data["reason"], "locked_out")

    def test_changing_the_password_is_challenged(self):
        """The route already requires the current password. The second factor
        proves what a password alone cannot."""
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
        """The password is checked before the gate, so the retry does not
        need a second factor again."""
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
        """A PATCH that repeats the stored email changes nothing to gate.

        It carries the password the serializer requires with an email, so the
        write does not fail for a reason unrelated to the gate.
        """
        response = self._patch_email(
            {"email": self.user.email, "password": self.login_password}
        )

        self.assertEqual(response.status_code, 200)
