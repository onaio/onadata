import base64
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.http.request import HttpRequest
from django.test import TestCase, override_settings
from django.utils import timezone

import jwt
from kombu.exceptions import OperationalError
from oauth2_provider.models import AccessToken, get_application_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from onadata.apps.api.models.temp_token import TempToken
from onadata.libs.authentication import (
    DigestAuthentication,
    LockoutBasicAuthentication,
    MasterReplicaOAuth2Validator,
    TempTokenAuthentication,
    TempTokenURLParameterAuthentication,
    add_login_attempt,
    assert_not_locked_out,
    check_lockout,
    get_api_token,
    get_client_ip,
    get_lockout_username,
    is_lockout_excluded_path,
)
from onadata.libs.utils.cache_tools import LOCKOUT_IP, safe_cache_set, safe_key
from onadata.libs.utils.common_tags import API_TOKEN

JWT_SECRET_KEY = getattr(settings, "JWT_SECRET_KEY", "jwt")
JWT_ALGORITHM = getattr(settings, "JWT_ALGORITHM", "HS256")


class TestGetAPIToken(TestCase):
    def test_expired_token(self):
        with self.assertRaisesRegex(AuthenticationFailed, "Token expired"):
            data = {
                API_TOKEN: "somekey",
                "exp": timezone.now() - timedelta(seconds=1),
            }
            jwt_data = jwt.encode(data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
            get_api_token(jwt_data)

    def test_invalid_token(self):
        with self.assertRaisesRegex(AuthenticationFailed, "Invalid token"):
            data = {API_TOKEN: "somekey", "aud": "unexpected-audience"}
            jwt_data = jwt.encode(data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
            get_api_token(jwt_data)

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
        extra = {"HTTP_AUTHORIZATION": f'Digest username="{trailing_space_name}",'}
        request = self.factory.get("/", **extra)

        # Assert that an exception is raised when trailing_spaces are
        # passed as a username
        with self.assertRaises(AuthenticationFailed):
            check_lockout(request)


class TestIsLockoutExcludedPath(TestCase):
    """Test is_lockout_excluded_path() function."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_true_for_excluded_openrosa_paths(self):
        """OpenRosa/Briefcase endpoints are exempt from lockout."""
        for path in (
            "/formList",
            "/bob/formList",
            "/submission",
            "/bob/submission",
            "/xformsManifest/123",
            "/123/form.xml",
            "/submissionList",
            "/downloadSubmission",
        ):
            with self.subTest(path=path):
                request = self.factory.get(path)
                self.assertTrue(is_lockout_excluded_path(request))

    def test_false_for_regular_paths(self):
        """Regular API paths are subject to lockout."""
        for path in ("/", "/api/v1/user.json", "/api/v1/forms"):
            with self.subTest(path=path):
                request = self.factory.get(path)
                self.assertFalse(is_lockout_excluded_path(request))

    def test_matches_excluded_segment_anywhere_in_path(self):
        """The exemption matches an excluded segment in any path position."""
        request = self.factory.get("/enketo/123/submission")
        self.assertTrue(is_lockout_excluded_path(request))


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


@override_settings(MAX_LOGIN_ATTEMPTS=3, LOCKOUT_TIME=1800)
class TestAddLoginAttempt(TestCase):
    """Test add_login_attempt() locks out, notifies the owner and logs it."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        User.objects.create_user(
            username="bob", email="bob@example.com", password="secret"
        )
        email_patcher = patch(
            "onadata.libs.authentication.send_account_lockout_email.apply_async"
        )
        self.send_email = email_patcher.start()
        self.addCleanup(email_patcher.stop)
        log_patcher = patch("onadata.libs.authentication.sentry_logger")
        self.sentry_logger = log_patcher.start()
        self.addCleanup(log_patcher.stop)

    def _fail_until_locked_out(self, ip_address):
        for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):
            add_login_attempt(ip_address, "bob")
        with self.assertRaises(AuthenticationFailed):
            add_login_attempt(ip_address, "bob")

    def test_lockouts_from_other_ips_do_not_email_again(self):
        """An account locked out from many IPs gets one start and one end
        email, not a pair per IP."""
        self._fail_until_locked_out("1.2.3.4")
        self.assertEqual(self.send_email.call_count, 2)

        self._fail_until_locked_out("5.6.7.8")
        self.assertEqual(self.send_email.call_count, 2)

    def test_the_interval_does_not_hold_back_other_accounts(self):
        self._fail_until_locked_out("1.2.3.4")
        User.objects.create_user(
            username="alice", email="alice@example.com", password="secret"
        )
        for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):
            add_login_attempt("1.2.3.4", "alice")
        with self.assertRaises(AuthenticationFailed):
            add_login_attempt("1.2.3.4", "alice")

        self.assertEqual(self.send_email.call_count, 4)

    @override_settings(LOCKOUT_EMAIL_INTERVAL=1)
    def test_emails_again_once_the_interval_has_passed(self):
        self._fail_until_locked_out("1.2.3.4")
        self.assertEqual(self.send_email.call_count, 2)

        time.sleep(1.1)
        self._fail_until_locked_out("5.6.7.8")
        self.assertEqual(self.send_email.call_count, 4)

    def test_a_failed_send_still_locks_out_and_retries_on_the_next_lockout(self):
        self.send_email.side_effect = [OperationalError("broker down"), None, None]
        with self.assertLogs("onadata.libs.authentication", level="ERROR"):
            self._fail_until_locked_out("1.2.3.4")
        self.assertFalse(self.sentry_logger.info.call_args.kwargs["email_sent"])

        self._fail_until_locked_out("5.6.7.8")
        self.assertEqual(self.send_email.call_count, 3)

    def test_lockouts_of_unknown_accounts_are_not_reported(self):
        """Usernames that match no account are attacker-chosen strings."""
        for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):
            add_login_attempt("1.2.3.4", "nobody")
        with self.assertRaises(AuthenticationFailed):
            add_login_attempt("1.2.3.4", "nobody")

        self.send_email.assert_not_called()
        self.sentry_logger.info.assert_not_called()

    def test_every_lockout_is_logged_to_sentry(self):
        """Lockouts whose email was suppressed are still logged."""
        self._fail_until_locked_out("1.2.3.4")
        self._fail_until_locked_out("5.6.7.8")

        self.assertEqual(
            [call.kwargs for call in self.sentry_logger.info.call_args_list],
            [
                {
                    "username": "bob",
                    "ip_address": "1.2.3.4",
                    "attempts": 3,
                    "email_sent": True,
                },
                {
                    "username": "bob",
                    "ip_address": "5.6.7.8",
                    "attempts": 3,
                    "email_sent": False,
                },
            ],
        )

    def test_attempts_without_a_username_do_not_create_a_lockout(self):
        """Excluded paths count attempts with no IP or username; a lockout
        keyed on neither would lock nobody out."""
        for _ in range(settings.MAX_LOGIN_ATTEMPTS):
            add_login_attempt(None, None)

        self.assertEqual(add_login_attempt(None, None), settings.MAX_LOGIN_ATTEMPTS + 1)
        self.assertIsNone(cache.get(safe_key(f"{LOCKOUT_IP}None-None")))

    def test_lockouts_without_a_client_ip_are_still_reported(self):
        """An IP that resolves to an empty string (``X-Real-Ip: ,1.2.3.4``)
        escapes enforcement, so the owner must still hear about it."""
        for _ in range(settings.MAX_LOGIN_ATTEMPTS):
            add_login_attempt("", "bob")

        self.assertEqual(self.send_email.call_count, 2)
        self.sentry_logger.info.assert_called_once()

    def test_attempts_racing_past_the_threshold_create_one_lockout(self):
        """Concurrent requests can each read the lockout key before any of
        them writes it; only one of them may create the lockout."""
        for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):
            add_login_attempt("1.2.3.4", "bob")
        lockout_key = safe_key(f"{LOCKOUT_IP}1.2.3.4-bob")

        def read_before_lockout_written(key, default=None):
            return None if key == lockout_key else cache.get(key, default)

        # The stale read also hides the lockout from assert_not_locked_out,
        # so neither call raises.
        with patch(
            "onadata.libs.authentication.safe_cache_get",
            side_effect=read_before_lockout_written,
        ):
            add_login_attempt("1.2.3.4", "bob")
            add_login_attempt("1.2.3.4", "bob")

        self.assertEqual(self.send_email.call_count, 2)
        self.assertEqual(self.sentry_logger.info.call_count, 1)
        self.assertIsNotNone(cache.get(lockout_key))


class TestMasterReplicaOAuth2Validator(TestCase):
    @patch("onadata.libs.authentication.AccessToken")
    def test_reads_from_master(self, mock_token_class):
        def is_valid_mock(*args, **kwargs):
            return True

        user = User.objects.create_user(username="bob")
        token = MagicMock()
        token.is_valid = is_valid_mock
        token.user = user
        token.user_id = user.pk
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

    def test_rejects_inactive_user_access_token(self):
        user = User.objects.create_user(username="inactive-oauth")
        application_model = get_application_model()
        application = application_model.objects.create(
            name="inactive-oauth-app",
            user=user,
            client_id="inactive-oauth-client",
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_PASSWORD,
        )
        access_token = AccessToken.objects.create(
            user=user,
            application=application,
            token="inactive-oauth-access",
            expires=timezone.now() + timedelta(days=1),
            scope="read write",
        )
        user.is_active = False
        user.save(update_fields=["is_active"])
        req = HttpRequest()

        self.assertFalse(
            MasterReplicaOAuth2Validator().validate_bearer_token(
                access_token.token, {}, req
            )
        )
        self.assertFalse(hasattr(req, "user"))

    def test_allows_userless_access_token(self):
        application_model = get_application_model()
        application = application_model.objects.create(
            name="userless-oauth-app",
            client_id="userless-oauth-client",
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
        )
        access_token = AccessToken.objects.create(
            application=application,
            token="userless-oauth-access",
            expires=timezone.now() + timedelta(days=1),
            scope="read write",
        )
        req = HttpRequest()

        self.assertTrue(
            MasterReplicaOAuth2Validator().validate_bearer_token(
                access_token.token, {}, req
            )
        )
        self.assertIsNone(req.user)


def _basic_header(username, password):
    """Build an HTTP Basic ``Authorization`` header value for credentials."""
    raw = f"{username}:{password}".encode("utf-8")
    return b"Basic " + base64.b64encode(raw)


MAX_LOGIN_ATTEMPTS = 3


@override_settings(MAX_LOGIN_ATTEMPTS=MAX_LOGIN_ATTEMPTS)
class TestLockoutBasicAuthentication(TestCase):
    """Test failed-login lockout on HTTP Basic authentication (ONADATA-1304)."""

    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.auth = LockoutBasicAuthentication()
        self.user = User.objects.create_user(
            username="bob", email="bob@example.com", password="secret"
        )

    def tearDown(self):
        cache.clear()

    def test_authenticates_with_valid_credentials(self):
        """Valid Basic credentials return the authenticated user."""
        request = self.factory.get(
            "/", HTTP_AUTHORIZATION=_basic_header("bob", "secret")
        )
        user, _auth = self.auth.authenticate(request)
        self.assertEqual(user, self.user)

    def test_rejects_inactive_user(self):
        """Inactive users cannot authenticate with valid Basic credentials."""
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        request = self.factory.get(
            "/", HTTP_AUTHORIZATION=_basic_header("bob", "secret")
        )

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_returns_none_without_basic_header(self):
        """Non-Basic requests are ignored so other authenticators can run."""
        request = self.factory.get("/", HTTP_AUTHORIZATION=b'Digest username="bob",')
        self.assertIsNone(self.auth.authenticate(request))

    def test_locks_out_after_max_failed_attempts(self):
        """Repeated wrong passwords lock the IP + username out."""
        header = _basic_header("bob", "wrong")
        for _i in range(MAX_LOGIN_ATTEMPTS):
            request = self.factory.get("/", HTTP_AUTHORIZATION=header)
            with self.assertRaises(AuthenticationFailed):
                self.auth.authenticate(request)

        # The IP + username is now locked out: even the correct password fails.
        request = self.factory.get(
            "/", HTTP_AUTHORIZATION=_basic_header("bob", "secret")
        )
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.authenticate(request)
        self.assertIn("Locked out", str(ctx.exception))

    def test_lockout_is_keyed_per_username(self):
        """Locking one username does not lock another from the same IP."""
        User.objects.create_user(username="alice", password="secret")
        for _i in range(MAX_LOGIN_ATTEMPTS):
            request = self.factory.get(
                "/", HTTP_AUTHORIZATION=_basic_header("bob", "wrong")
            )
            with self.assertRaises(AuthenticationFailed):
                self.auth.authenticate(request)

        # alice, same IP, is unaffected and authenticates normally.
        request = self.factory.get(
            "/", HTTP_AUTHORIZATION=_basic_header("alice", "secret")
        )
        user, _auth = self.auth.authenticate(request)
        self.assertEqual(user.username, "alice")

    def test_excluded_paths_are_not_locked_out(self):
        """OpenRosa endpoints (e.g. /submission) are exempt from lockout,
        mirroring DigestAuthentication, so high-frequency clients aren't locked
        out."""
        for _i in range(MAX_LOGIN_ATTEMPTS + 5):
            request = self.factory.post(
                "/submission", HTTP_AUTHORIZATION=_basic_header("bob", "wrong")
            )
            with self.assertRaises(AuthenticationFailed) as ctx:
                self.auth.authenticate(request)
            # Always the plain credential error, never a lockout.
            self.assertNotIn("Locked out", str(ctx.exception))

        # The correct password still works on the excluded path.
        request = self.factory.post(
            "/submission", HTTP_AUTHORIZATION=_basic_header("bob", "secret")
        )
        user, _auth = self.auth.authenticate(request)
        self.assertEqual(user, self.user)

    def test_lockout_counter_canonicalises_identifier(self):
        """Case/email variants of a username share one lockout counter."""
        # Mix bare username, uppercase, and email forms — all resolve to "bob".
        identifiers = (["BOB", "bob@example.com"] * MAX_LOGIN_ATTEMPTS)[
            :MAX_LOGIN_ATTEMPTS
        ]
        for identifier in identifiers:
            request = self.factory.get(
                "/", HTTP_AUTHORIZATION=_basic_header(identifier, "wrong")
            )
            with self.assertRaises(AuthenticationFailed):
                self.auth.authenticate(request)

        # The canonical account is now locked out despite the varied inputs.
        request = self.factory.get(
            "/", HTTP_AUTHORIZATION=_basic_header("bob", "secret")
        )
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.authenticate(request)
        self.assertIn("Locked out", str(ctx.exception))


@override_settings(MAX_LOGIN_ATTEMPTS=MAX_LOGIN_ATTEMPTS)
class TestLockoutTokenView(TestCase):
    """Test failed-login lockout on the OAuth2 password grant (/o/token/)."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="bob", email="bob@example.com", password="secret"
        )
        application_model = get_application_model()
        self.client_secret = "test-client-secret"
        self.application = application_model(
            name="password-grant-app",
            user=self.user,
            client_id="test-client-id",
            client_secret=self.client_secret,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_PASSWORD,
        )
        self.application.save()

    def tearDown(self):
        cache.clear()

    def _token_request(self, password):
        return self.client.post(
            "/o/token/",
            {
                "grant_type": "password",
                "username": "bob",
                "password": password,
                "client_id": "test-client-id",
                "client_secret": self.client_secret,
            },
        )

    def test_locks_out_after_max_failed_password_grants(self):
        """Repeated wrong passwords lock the IP + username out of /o/token/."""
        for _i in range(MAX_LOGIN_ATTEMPTS):
            response = self._token_request("wrong")
            self.assertNotEqual(response.status_code, 200)

        # Even the correct password is now rejected with the lockout response.
        response = self._token_request("secret")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"], "locked_out")

    def test_valid_password_grant_issues_token(self):
        """Valid credentials still return an access token through the view."""
        response = self._token_request("secret")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())

    def test_failure_below_threshold_returns_oauth_error(self):
        """A failed attempt below the threshold returns the normal OAuth error,
        not the lockout response."""
        response = self._token_request("wrong")
        self.assertEqual(response.status_code, 400)
        self.assertNotEqual(response.status_code, 429)
        # The account is not yet locked: the correct password still works.
        response = self._token_request("secret")
        self.assertEqual(response.status_code, 200)
