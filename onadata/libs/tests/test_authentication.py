from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
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
    TempTokenAuthentication,
    TempTokenURLParameterAuthentication,
    assert_not_locked_out,
    check_lockout,
    get_api_token,
    get_client_ip,
    get_lockout_username,
)
from onadata.libs.utils.cache_tools import LOCKOUT_IP, safe_cache_set, safe_key
from onadata.libs.utils.common_tags import API_TOKEN

JWT_SECRET_KEY = getattr(settings, "JWT_SECRET_KEY", "jwt")
JWT_ALGORITHM = getattr(settings, "JWT_ALGORITHM", "HS256")


class TestGetAPIToken(TestCase):
    def test_non_existent_token(self):
        with self.assertRaisesRegex(AuthenticationFailed, "Invalid token"):
            data = {API_TOKEN: "nonexistenttoken"}
            jwt_data = jwt.encode(data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
            get_api_token(jwt_data)

    def test_bad_signature(self):
        with self.assertRaisesRegex(
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


class TestGetClientIp(TestCase):
    """Test get_client_ip() function."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_uses_remote_addr_by_default(self):
        """REMOTE_ADDR is used when no X-Real-Ip header is present."""
        request = self.factory.get("/")
        self.assertNotIn("HTTP_X_REAL_IP", request.META)
        self.assertEqual(get_client_ip(request), request.META.get("REMOTE_ADDR"))

    def test_prefers_x_real_ip(self):
        """The X-Real-Ip header takes precedence over REMOTE_ADDR."""
        request = self.factory.get("/", HTTP_X_REAL_IP="1.2.3.4")
        self.assertEqual(get_client_ip(request), "1.2.3.4")

    def test_returns_first_of_comma_separated_x_real_ip(self):
        """Only the first address in a comma-separated X-Real-Ip is returned."""
        request = self.factory.get("/", HTTP_X_REAL_IP="1.2.3.4, 5.6.7.8")
        self.assertEqual(get_client_ip(request), "1.2.3.4")


class TestAssertNotLockedOut(TestCase):
    """Test assert_not_locked_out() function."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @staticmethod
    def _lock_out(ip_address, username):
        safe_cache_set(
            safe_key(f"{LOCKOUT_IP}{ip_address}-{username}"),
            datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            getattr(settings, "LOCKOUT_TIME", 1800),
        )

    def test_does_nothing_when_not_locked_out(self):
        """No exception is raised when the IP + username is not locked out."""
        self.assertIsNone(assert_not_locked_out("1.2.3.4", "bob"))

    def test_does_nothing_when_identifier_missing(self):
        """No lockout is checked when either identifier is missing."""
        self._lock_out("1.2.3.4", "bob")
        self.assertIsNone(assert_not_locked_out("1.2.3.4", None))
        self.assertIsNone(assert_not_locked_out(None, "bob"))
        self.assertIsNone(assert_not_locked_out(None, None))

    def test_raises_when_locked_out(self):
        """AuthenticationFailed is raised when the IP + username is locked out."""
        self._lock_out("1.2.3.4", "bob")
        with self.assertRaises(AuthenticationFailed):
            assert_not_locked_out("1.2.3.4", "bob")

    def test_lockout_is_keyed_per_ip_and_username(self):
        """A lockout for one IP + username does not affect another."""
        self._lock_out("1.2.3.4", "bob")
        # Different username, same IP -> not locked out
        self.assertIsNone(assert_not_locked_out("1.2.3.4", "alice"))
        # Different IP, same username -> not locked out
        self.assertIsNone(assert_not_locked_out("5.6.7.8", "bob"))


class TestGetLockoutUsername(TestCase):
    """Test get_lockout_username() canonicalises submitted identifiers."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="bob", email="bob@example.com", password="secret"
        )

    def test_returns_canonical_username_for_case_variant(self):
        """A different-case username resolves to the stored username."""
        self.assertEqual(get_lockout_username("BOB"), "bob")
        self.assertEqual(get_lockout_username("Bob"), "bob")

    def test_returns_canonical_username_for_email(self):
        """An email identifier resolves to the account's username."""
        self.assertEqual(get_lockout_username("bob@example.com"), "bob")
        self.assertEqual(get_lockout_username("BOB@EXAMPLE.COM"), "bob")

    def test_falls_back_to_submitted_value_for_unknown_user(self):
        """An unmatched identifier is returned unchanged so it is still
        throttled."""
        self.assertEqual(get_lockout_username("nobody"), "nobody")


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
