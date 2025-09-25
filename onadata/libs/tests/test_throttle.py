from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.test import TestCase, override_settings

from rest_framework.test import APIRequestFactory

from onadata.libs.throttle import (
    CustomScopedRateThrottle,
    RequestHeaderThrottle,
    UserIDThrottle,
)


class CustomScopedRateThrottleTest(TestCase):
    def setUp(self):
        # Reset the cache so that no throttles will be active
        cache.clear()
        self.factory = APIRequestFactory()
        self.throttle = CustomScopedRateThrottle()

    def test_anonymous_users(self):
        """Anonymous users  get throttled base on URI path"""
        request = self.factory.get("/enketo/1234/submission")
        request.user = AnonymousUser()
        self.throttle.scope = "submission"
        cache_key = self.throttle.get_cache_key(request, None)
        self.assertEqual(
            cache_key, "throttle_submission_/enketo/1234/submission_127.0.0.1"
        )

    def test_authenticated_users(self):
        """Authenticated users  get throttled base on user id"""
        request = self.factory.get("/enketo/1234/submission")
        user, _created = User.objects.get_or_create(username="throttleduser")
        request.user = user
        self.throttle.scope = "submission"
        cache_key = self.throttle.get_cache_key(request, None)
        self.assertEqual(cache_key, f"throttle_submission_{user.id}")


class ThrottlingTests(TestCase):
    def setUp(self):
        # Reset the cache so that no throttles will be active
        cache.clear()
        self.factory = APIRequestFactory()
        self.throttle = RequestHeaderThrottle()
        self.extra = {"HTTP_USER_AGENT": "Google-HTTP-Java-Client/1.35.0 (gzip)"}

    @override_settings(
        THROTTLE_HEADERS={
            "HTTP_USER_AGENT": "Google-HTTP-Java-Client/1.35.0 (gzip)",
        }
    )
    def test_requests_are_throttled(self):
        request = self.factory.get("/", **self.extra)
        # get cached key
        key = self.throttle.get_cache_key(request, None)
        self.assertEqual(key, "throttle_header_Google-HTTP-Java-Client/1.35.0(gzip)")

    @override_settings(
        THROTTLE_HEADERS={
            "HTTP_USER_AGENT": ["Google-HTTP-Java-Client/1.35.0 (gzip)", "Mozilla/5.0"],
        }
    )
    def test_request_throttling_multiple_headers(self):
        extra = {"HTTP_USER_AGENT": "Mozilla/5.0"}
        request = self.factory.get("/", **extra)
        key = self.throttle.get_cache_key(request, None)
        self.assertEqual(key, "throttle_header_Mozilla/5.0")

        extra = {"HTTP_USER_AGENT": "Google-HTTP-Java-Client/1.35.0 (gzip)"}
        request = self.factory.get("/", **extra)
        key = self.throttle.get_cache_key(request, None)
        self.assertEqual(key, "throttle_header_Google-HTTP-Java-Client/1.35.0(gzip)")


class UserIDThrottleTest(TestCase):
    def setUp(self):
        # Reset the cache so that no throttles will be active
        cache.clear()
        self.factory = APIRequestFactory()
        self.throttle = UserIDThrottle()

    def test_authenticated_user_throttled_by_user_id(self):
        """Authenticated users should be throttled by their user ID"""
        request = self.factory.get("/api/test")
        user, _created = User.objects.get_or_create(username="testuser")
        request.user = user

        cache_key = self.throttle.get_cache_key(request, None)
        expected_key = f"throttle_user_{user.id}"
        self.assertEqual(cache_key, expected_key)

    def test_anonymous_user_not_throttled(self):
        """Anonymous users should not be throttled"""
        request = self.factory.get("/api/test")
        request.user = AnonymousUser()

        cache_key = self.throttle.get_cache_key(request, None)
        self.assertIsNone(cache_key)

    def test_different_users_get_different_cache_keys(self):
        """Different authenticated users should get different cache keys"""
        request1 = self.factory.get("/api/test")
        user1, _created = User.objects.get_or_create(username="user1")
        request1.user = user1

        request2 = self.factory.get("/api/test")
        user2, _created = User.objects.get_or_create(username="user2")
        request2.user = user2

        cache_key1 = self.throttle.get_cache_key(request1, None)
        cache_key2 = self.throttle.get_cache_key(request2, None)

        self.assertNotEqual(cache_key1, cache_key2)
        self.assertEqual(cache_key1, f"throttle_user_{user1.id}")
        self.assertEqual(cache_key2, f"throttle_user_{user2.id}")
