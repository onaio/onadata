"""
Tests that an OAuth token can't be swapped for the account's own credentials
at /api/v1/user.
"""

from datetime import timedelta

from django.utils import timezone

from oauth2_provider.models import AccessToken, get_application_model
from rest_framework.authtoken.models import Token

from onadata.apps.api.models.odk_token import ODKToken
from onadata.apps.api.models.temp_token import TempToken
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet

REFUSED = "OAuth applications cannot obtain API or ODK tokens."


class TestConnectViewSetOAuth(TestAbstractViewSet):
    """An OAuth token reads the profile but gets no API, temp or ODK token.
    Each test repeats the request with the API token to show the same call
    still hands the credential to a non-OAuth caller."""

    def setUp(self):
        super().setUp()
        application_model = get_application_model()
        application = application_model.objects.create(
            name="third-party-app",
            user=self.user,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_AUTHORIZATION_CODE,
            redirect_uris="https://app.example/callback",
        )
        token = AccessToken.objects.create(
            user=self.user,
            application=application,
            token="connect-oauth-access",
            expires=timezone.now() + timedelta(hours=1),
            scope="read write",
        )
        self.bearer = {"HTTP_AUTHORIZATION": f"Bearer {token.token}"}

    def _call(self, method, handler, headers):
        view = ConnectViewSet.as_view({method: handler})
        request = getattr(self.factory, method)("/", **headers)
        request.session = self.client.session
        return view(request)

    def test_the_profile_carries_no_tokens_for_an_oauth_caller(self):
        TempToken.objects.filter(user=self.user).delete()

        response = self._call("get", "list", self.bearer)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "bob")
        self.assertNotIn("api_token", response.data)
        self.assertNotIn("temp_token", response.data)
        self.assertFalse(TempToken.objects.filter(user=self.user).exists())

        response = self._call("get", "list", self.extra)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["api_token"], self.user.auth_token.key)
        self.assertIn("temp_token", response.data)

    def test_posting_to_the_profile_carries_no_tokens_for_an_oauth_caller(self):
        response = self._call("post", "create", self.bearer)

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("api_token", response.data)
        self.assertNotIn("temp_token", response.data)

        response = self._call("post", "create", self.extra)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["api_token"], self.user.auth_token.key)
        self.assertIn("temp_token", response.data)

    def test_an_oauth_caller_cannot_regenerate_the_api_token(self):
        key = self.user.auth_token.key

        response = self._call("get", "regenerate_auth_token", self.bearer)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(str(response.data["detail"]), REFUSED)
        self.assertEqual(Token.objects.get(user=self.user).key, key)

        response = self._call("get", "regenerate_auth_token", self.extra)

        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(Token.objects.get(user=self.user).key, key)

    def test_an_oauth_caller_cannot_get_an_odk_token(self):
        self.assertFalse(ODKToken.objects.filter(user=self.user).exists())

        for method in ("get", "post"):
            response = self._call(method, "odk_token", self.bearer)

            self.assertEqual(response.status_code, 403, method)
            self.assertEqual(str(response.data["detail"]), REFUSED)
        self.assertFalse(ODKToken.objects.filter(user=self.user).exists())

        response = self._call("get", "odk_token", self.extra)

        self.assertEqual(response.status_code, 200)
        self.assertIn("odk_token", response.data)

        response = self._call("post", "odk_token", self.extra)

        self.assertEqual(response.status_code, 201)
        self.assertIn("odk_token", response.data)

    def test_changing_the_password_rotates_but_does_not_return_tokens(self):
        view = UserProfileViewSet.as_view({"post": "change_password"})
        old_key = self.user.auth_token.key
        data = {"current_password": "bobbob", "new_password": "bobbob1"}

        response = view(self.factory.post("/", data=data, **self.bearer), user="bob")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"username": "bob"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("bobbob1"))
        self.assertNotEqual(Token.objects.get(user=self.user).key, old_key)

        api_token = {"HTTP_AUTHORIZATION": f"Token {self.user.auth_token.key}"}
        data = {"current_password": "bobbob1", "new_password": "bobbob2"}
        response = view(self.factory.post("/", data=data, **api_token), user="bob")

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.data)
        self.assertIn("temp_token", response.data)
