# -*- coding: utf-8 -*-
"""
Tests for the step-up gate on changing an account's username.
"""

from unittest.mock import patch

from oidc.stepup_grants import issue_grant
from registration.models import RegistrationProfile

from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    StepUpGateTestCase,
    gating,
)
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet

CHANGE_USERNAME = "change-username"
NEW_USERNAME = "robert"


@gating(CHANGE_USERNAME)
class TestChangeUsernameGate(StepUpGateTestCase):
    """Renaming the account moves every URL, share and login built on the
    old name, so a stolen session alone must not be able to do it."""

    def setUp(self):
        super().setUp()
        # A full PUT re-sends the email, which reissues the activation key.
        RegistrationProfile.objects.create_profile(self.user)
        self.view = UserProfileViewSet.as_view(
            {"patch": "partial_update", "put": "update"}
        )
        self.assertEqual(self.user.username, "bob")

    def _patch(self, data, headers=None):
        request = self.factory.patch(
            "/", data=data, format="json", **{**self.extra, **(headers or {})}
        )
        return self.view(request, user=self.user.username)

    def _put(self, data):
        """A full write that repeats every stored value unless ``data``
        changes it. It sends the password the serializer requires with an
        email."""
        payload = {
            "username": self.user.username,
            "email": self.user.email,
            "password": self.login_password,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            **data,
        }
        request = self.factory.put("/", data=payload, format="json", **self.extra)
        return self.view(request, user=self.user.username)

    def _stored_username(self):
        self.user.refresh_from_db()
        return self.user.username

    def test_changing_the_username_without_a_grant_is_challenged(self):
        response = self._patch({"username": NEW_USERNAME})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], CHANGE_USERNAME)
        self.assertEqual(self._stored_username(), "bob")

    @patch(
        "onadata.libs.serializers.user_profile_serializer."
        "send_verification_email.delay"
    )
    def test_a_put_changing_the_username_without_a_grant_is_challenged(
        self, _send_verification
    ):
        response = self._put({"username": NEW_USERNAME})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], CHANGE_USERNAME)
        self.assertEqual(self._stored_username(), "bob")

    def test_a_grant_lets_the_username_change_through(self):
        grant = issue_grant(self.user.pk, CHANGE_USERNAME)

        response = self._patch(
            {"username": NEW_USERNAME}, {"HTTP_X_STEP_UP_GRANT": grant}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._stored_username(), NEW_USERNAME)

    def test_a_username_differing_only_as_the_serializer_cleans_it_is_not_challenged(
        self,
    ):
        """The serializer trims and lowercases, so " BOB " writes "bob" back
        unchanged. Comparing the raw value would challenge it."""
        self.assertEqual(self._patch({"username": NEW_USERNAME}).status_code, 401)

        response = self._patch({"username": " BOB "})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._stored_username(), "bob")

    @patch(
        "onadata.libs.serializers.user_profile_serializer."
        "send_verification_email.delay"
    )
    def test_a_put_echoing_the_username_is_not_challenged(self, _send_verification):
        response = self._put({"city": "Nairobi"})

        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.city, "Nairobi")

    def test_an_unrelated_change_is_not_challenged(self):
        self.assertEqual(self._patch({"username": NEW_USERNAME}).status_code, 401)

        response = self._patch({"city": "Nairobi"})

        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.city, "Nairobi")
