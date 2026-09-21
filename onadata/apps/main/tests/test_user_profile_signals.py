"""Tests for the UserProfile post_save signal receivers."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

import jwt
import requests
from httmock import HTTMock, all_requests
from rest_framework.authtoken.models import Token

from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs.utils.common_tags import API_TOKEN, ONADATA_KOBOCAT_AUTH_HEADER

User = get_user_model()


class SetKpiFormbuilderPermissionsTestCase(TestCase):
    """set_kpi_formbuilder_permissions() on UserProfile creation.

    Depends on KPI_FORMBUILDER_URL being set; the receiver is a no-op without
    it, so every test overrides the setting.
    """

    def setUp(self):
        super().setUp()
        self.captured_headers = {}

    @all_requests
    def grant_perms(self, url, request):  # pylint: disable=unused-argument
        """Stand in for the KPI formbuilder grant-perms endpoint."""
        # Kept as the case-insensitive mapping requests built it as.
        self.captured_headers = request.headers
        response = requests.Response()
        response.status_code = 201

        return response

    def _create_profile(self, user):
        with (
            HTTMock(self.grant_perms),
            self.settings(KPI_FORMBUILDER_URL="http://test_formbuilder$"),
        ):
            return UserProfile.objects.create(user=user)

    def _user_without_auth_token(self):
        user = User.objects.create_user(username="alice", password="alice")
        # A Token is created by a post_save signal on User; drop it to model a
        # user whose token was deleted and never regenerated. Re-fetch so the
        # deleted token is not still cached on the instance.
        Token.objects.filter(user=user).delete()
        user = User.objects.get(pk=user.pk)
        self.assertFalse(Token.objects.filter(user=user).exists())

        return user

    def test_profile_created_for_user_without_auth_token(self):
        """A profile can be created for a user whose auth token is missing."""
        user = self._user_without_auth_token()

        profile = self._create_profile(user)

        self.assertEqual(profile.user, user)
        self.assertTrue(Token.objects.filter(user=user).exists())

    def test_kpi_request_signed_with_the_created_token(self):
        """The KPI auth header carries the token the receiver just created."""
        user = self._user_without_auth_token()

        self._create_profile(user)

        payload = jwt.decode(
            self.captured_headers[ONADATA_KOBOCAT_AUTH_HEADER],
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        self.assertEqual(payload[API_TOKEN], Token.objects.get(user=user).key)

    def test_existing_auth_token_is_reused(self):
        """A user who already has a token keeps it when the profile is created."""
        user = User.objects.create_user(username="alice", password="alice")
        existing_key = Token.objects.get(user=user).key

        self._create_profile(user)

        self.assertEqual(Token.objects.get(user=user).key, existing_key)
