from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.core.cache import cache
from django.contrib.auth.models import User

from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from onadata.libs.utils.cache_tools import safe_key
from onadata.apps.api.models.temp_token import TempToken
from onadata.libs.authentication import (
    DigestAuthentication,
    TempTokenAuthentication,
    TempTokenURLParameterAuthentication,
    check_lockout,
    login_attempts
)


class TestPermissions(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.extra = {"HTTP_AUTHORIZATION": b"digest &#x0030;"}

    def test_invalid_bytes_in_digest(self):
        digest_auth = DigestAuthentication()
        request = self.factory.get("/", **self.extra)
        self.assertRaises(
            AuthenticationFailed, digest_auth.authenticate, request
        )


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
            u"Token expired",
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
            u"User inactive or deleted",
            self.temp_token_authentication.authenticate_credentials,
            temp_token.key,
        )

    def test_invalid_temp_token(self):
        self.assertRaisesMessage(
            AuthenticationFailed,
            u"Invalid token",
            self.temp_token_authentication.authenticate_credentials,
            "123",
        )

    def test_authenticates_if_token_is_valid(self):
        user, created = User.objects.get_or_create(username="temp")
        token, created = TempToken.objects.get_or_create(user=user)

        returned_user, returned_token = self.temp_token_authentication\
            .authenticate_credentials(token.key)
        self.assertEquals(user, returned_user)
        self.assertEquals(token, returned_token)


class TestTempTokenURLParameterAuthentication(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_returns_false_if_no_param(self):
        temp_token_param_authentication = TempTokenURLParameterAuthentication()
        request = self.factory.get("/export/123")
        self.assertEqual(
            temp_token_param_authentication.authenticate(request), None
        )


class TestLockout(TestCase):
    """Test user lockout functions.
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        self.extra = {"HTTP_AUTHORIZATION": b'Digest username="bob",'}

    def test_check_lockout(self):
        """Test check_lockout() function."""
        request = self.factory.get("/formList", **self.extra)
        self.assertIsNone(check_lockout(request))

        request = self.factory.get("/bob/formList", **self.extra)
        self.assertIsNone(check_lockout(request))

        request = self.factory.get("/submission", **self.extra)
        self.assertIsNone(check_lockout(request))

        request = self.factory.get("/bob/submission", **self.extra)
        self.assertIsNone(check_lockout(request))

        request = self.factory.get("/123/form.xml", **self.extra)
        self.assertIsNone(check_lockout(request))

        request = self.factory.get("/xformsManifest/123", **self.extra)
        self.assertIsNone(check_lockout(request))

        request = self.factory.get(
            "/", **{"HTTP_AUTHORIZATION": b"Digest bob"}
        )
        self.assertIsNone(check_lockout(request))

        request = self.factory.get("/", **self.extra)
        self.assertEqual(check_lockout(request), "bob")

    def test_exception_on_username_with_whitespaces(self):
        """
        Test the check_lockout properly handles usernames with
        trailing whitespaces
        """
        trailing_space_name = ' ' * 300
        extra = {
            "HTTP_AUTHORIZATION": f'Digest username="{ trailing_space_name }",'
        }
        request = self.factory.get("/", **extra)

        # Assert that an exception is raised when trailing_spaces are
        # passed as a username
        with self.assertRaises(AuthenticationFailed):
            check_lockout(request)

    def test_lockout_applies_against_username_and_email(self):
        """
        Test that login attempts increments
        if a user logins in with their email or their username
        """
        user, created = User.objects.get_or_create(
            username="temp",
            email="temp@ona.io")

        # clear cache
        cache.delete(safe_key("login_attempts-temp"))
        cache.delete(safe_key("lockout_user-temp"))
        self.assertIsNone(cache.get(safe_key('login_attempts-temp')))
        self.assertIsNone(cache.get(safe_key('lockout_user-temp')))

        extra = {
            "HTTP_AUTHORIZATION": f'Digest username="temp",'
        }
        request = self.factory.get("/", **extra)
        self.assertEqual(login_attempts(request), 1)

        # Make another request using the email to log in
        extra = {
            "HTTP_AUTHORIZATION": f'Digest username="temp@ona.io",'
        }

        request = self.factory.get("/", **extra)
        self.assertEqual(login_attempts(request), 2)
