from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase, override_settings

from rest_framework.test import APIRequestFactory

from onadata.libs.throttle import RequestHeaderThrottle, CustomScopedRateThrottle

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
            cache_key,
            "throttle_submission_/enketo/1234/submission_127.0.0.1"
        )

    def test_authenticated_users(self):
        """Authenticated users  get throttled base on user id"""
        request = self.factory.get("/enketo/1234/submission")
        user, _created = User.objects.get_or_create(username='throttleduser')
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
