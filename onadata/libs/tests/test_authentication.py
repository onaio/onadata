from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth.models import User
from django.http.request import HttpRequest
from django.test import TestCase

import jwt
from oauth2_provider.models import AccessToken
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from onadata.apps.api.models.temp_token import TempToken
from onadata.libs.authentication import (
    DigestAuthentication,
    MasterReplicaOAuth2Validator,
    StrictOAuth2Authentication,
    TempTokenAuthentication,
    TempTokenURLParameterAuthentication,
    check_lockout,
    get_api_token,
)
from onadata.libs.utils.common_tags import API_TOKEN

JWT_SECRET_KEY = getattr(settings, "JWT_SECRET_KEY", "jwt")
JWT_ALGORITHM = getattr(settings, "JWT_ALGORITHM", "HS256")


class TestGetAPIToken(TestCase):
    def test_non_existent_token(self):
        with self.assertRaisesRegexp(AuthenticationFailed, "Invalid token"):
            data = {API_TOKEN: "nonexistenttoken"}
            jwt_data = jwt.encode(data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
            get_api_token(jwt_data)

    def test_bad_signature(self):
        with self.assertRaisesRegexp(
            AuthenticationFailed, "JWT DecodeError: Signature verification failed"
        ):
            data = {API_TOKEN: "somekey"}
            jwt_data = jwt.encode(data, "wrong", algorithm=JWT_ALGORITHM)
            get_api_token(jwt_data)


class TestPermissions(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.extra = {"HTTP_AUTHORIZATION": b"digest &#x0030;"}

    def test_invalid_bytes_in_digest(self):
        digest_auth = DigestAuthentication()
        request = self.factory.get("/", **self.extra)
        self.assertRaises(AuthenticationFailed, digest_auth.authenticate, request)


class TestTempTokenAuthentication(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.temp_token_authentication = TempTokenAuthentication()

    def test_expired_temp_token(self):
        validity_period = getattr(settings, "DEFAULT_TEMP_TOKEN_EXPIRY_TIME")
        time_to_subtract = validity_period + 1
        user, created = User.objects.get_or_create(username="temp")
        temp_token, created = TempToken.objects.get_or_create(user=user)
        expired_time = temp_token.created - timedelta(seconds=time_to_subtract)
        temp_token.created = expired_time

        temp_token.save()
        self.assertRaisesMessage(
            AuthenticationFailed,
            "Token expired",
            self.temp_token_authentication.authenticate_credentials,
            temp_token.key,
        )

    def test_inactive_user(self):
        user, created = User.objects.get_or_create(username="temp")
        temp_token, created = TempToken.objects.get_or_create(user=user)
        user.is_active = False
        user.save()
        self.assertRaisesMessage(
            AuthenticationFailed,
            "User inactive or deleted",
            self.temp_token_authentication.authenticate_credentials,
            temp_token.key,
        )

    def test_invalid_temp_token(self):
        self.assertRaisesMessage(
            AuthenticationFailed,
            "Invalid token",
            self.temp_token_authentication.authenticate_credentials,
            "123",
        )

    def test_authenticates_if_token_is_valid(self):
        user, created = User.objects.get_or_create(username="temp")
        token, created = TempToken.objects.get_or_create(user=user)

        (
            returned_user,
            returned_token,
        ) = self.temp_token_authentication.authenticate_credentials(token.key)
        self.assertEqual(user, returned_user)
        self.assertEqual(token, returned_token)


class TestTempTokenURLParameterAuthentication(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_returns_false_if_no_param(self):
        temp_token_param_authentication = TempTokenURLParameterAuthentication()
        request = self.factory.get("/export/123")
        self.assertEqual(temp_token_param_authentication.authenticate(request), None)


class TestLockout(TestCase):
    """Test user lockout functions."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.extra = {"HTTP_AUTHORIZATION": b'Digest username="bob",'}

    def test_check_lockout(self):
        """Test check_lockout() function."""
        request = self.factory.get("/formList", **self.extra)
        self.assertEqual(check_lockout(request), (None, None))

        request = self.factory.get("/bob/formList", **self.extra)
        self.assertEqual(check_lockout(request), (None, None))

        request = self.factory.get("/submission", **self.extra)
        self.assertEqual(check_lockout(request), (None, None))

        request = self.factory.get("/bob/submission", **self.extra)
        self.assertEqual(check_lockout(request), (None, None))

        request = self.factory.get("/123/form.xml", **self.extra)
        self.assertEqual(check_lockout(request), (None, None))

        request = self.factory.get("/xformsManifest/123", **self.extra)
        self.assertEqual(check_lockout(request), (None, None))

        request = self.factory.get("/", **{"HTTP_AUTHORIZATION": b"Digest bob"})
        self.assertEqual(check_lockout(request), (None, None))

        request = self.factory.get("/", **self.extra)
        self.assertEqual(
            check_lockout(request), (request.META.get("REMOTE_ADDR"), "bob")
        )

        # Uses X_REAL_IP if present
        self.assertNotIn("HTTP_X_REAL_IP", request.META)
        extra = {"HTTP_X_REAL_IP": "1.2.3.4"}
        extra.update(self.extra)
        request = self.factory.get("/", **extra)

        self.assertEqual(check_lockout(request), ("1.2.3.4", "bob"))

    def test_exception_on_username_with_whitespaces(self):
        """
        Test the check_lockout properly handles usernames with
        trailing whitespaces
        """
        trailing_space_name = " " * 300
        extra = {"HTTP_AUTHORIZATION": f'Digest username="{ trailing_space_name }",'}
        request = self.factory.get("/", **extra)

        # Assert that an exception is raised when trailing_spaces are
        # passed as a username
        with self.assertRaises(AuthenticationFailed):
            check_lockout(request)


class TestMasterReplicaOAuth2Validator(TestCase):
    @patch("onadata.libs.authentication.AccessToken")
    def test_reads_from_master(self, mock_token_class):
        def is_valid_mock(*args, **kwargs):
            return True

        token = MagicMock()
        token.is_valid = is_valid_mock
        token.user = "bob"
        token.application = "bob-test"
        token.token = "abc"
        mock_token_class.DoesNotExist = AccessToken.DoesNotExist
        mock_token_class.objects.select_related(
            "application", "user"
        ).get.side_effect = [AccessToken.DoesNotExist, token]
        req = HttpRequest()
        self.assertTrue(
            MasterReplicaOAuth2Validator().validate_bearer_token(token, {}, req)
        )
        self.assertEqual(
            mock_token_class.objects.select_related(
                "application", "user"
            ).get.call_count,
            2,
        )
        self.assertEqual(req.access_token, token)
        self.assertEqual(req.user, token.user)


class TestStrictOAuth2Authentication(TestCase):
    """Test StrictOAuth2Authentication class."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.auth = StrictOAuth2Authentication()

    def test_returns_none_when_no_bearer_header(self):
        """Test returns None when no Bearer token is provided."""
        request = self.factory.get("/")
        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    def test_returns_none_when_different_auth_scheme(self):
        """Test returns None when Authorization header uses different scheme."""
        request = self.factory.get("/", HTTP_AUTHORIZATION="Token abc123")
        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    @patch("onadata.libs.authentication.OAuth2Authentication.authenticate")
    def test_raises_auth_failed_when_bearer_token_invalid(self, mock_authenticate):
        """Test raises AuthenticationFailed when Bearer token is invalid."""
        mock_authenticate.return_value = None
        request = self.factory.get("/", HTTP_AUTHORIZATION="Bearer invalid_token")
        request.oauth2_error = {"error_description": "The access token is invalid"}

        with self.assertRaises(AuthenticationFailed) as context:
            self.auth.authenticate(request)

        self.assertIn("access token is invalid", str(context.exception))

    @patch("onadata.libs.authentication.OAuth2Authentication.authenticate")
    def test_raises_auth_failed_when_bearer_token_expired(self, mock_authenticate):
        """Test raises AuthenticationFailed when Bearer token is expired."""
        mock_authenticate.return_value = None
        request = self.factory.get("/", HTTP_AUTHORIZATION="Bearer expired_token")
        request.oauth2_error = {"error_description": "The access token has expired"}

        with self.assertRaises(AuthenticationFailed) as context:
            self.auth.authenticate(request)

        self.assertIn("access token has expired", str(context.exception))

    @patch("onadata.libs.authentication.OAuth2Authentication.authenticate")
    def test_raises_auth_failed_with_default_message(self, mock_authenticate):
        """Test raises AuthenticationFailed with default message when no error_description."""
        mock_authenticate.return_value = None
        request = self.factory.get("/", HTTP_AUTHORIZATION="Bearer some_token")

        with self.assertRaises(AuthenticationFailed) as context:
            self.auth.authenticate(request)

        self.assertIn("Invalid or expired token", str(context.exception))

    @patch("onadata.libs.authentication.OAuth2Authentication.authenticate")
    def test_returns_user_and_token_when_valid(self, mock_authenticate):
        """Test returns (user, token) tuple when Bearer token is valid."""
        user = MagicMock()
        token = MagicMock()
        mock_authenticate.return_value = (user, token)
        request = self.factory.get("/", HTTP_AUTHORIZATION="Bearer valid_token")

        result = self.auth.authenticate(request)

        self.assertEqual(result, (user, token))
