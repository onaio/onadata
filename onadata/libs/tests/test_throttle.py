from django.core.cache import cache
from django.test import TestCase, override_settings

from rest_framework.test import APIRequestFactory

from onadata.libs.throttle import RequestHeaderThrottle, SubmissionURLThrottle


class SubmissionURLThrottleTests(TestCase):
    """
    Test Renderer class.
    """

    def setUp(self):
        """
        Reset the cache so that no throttles will be active
        """
        cache.clear()
        self.factory = APIRequestFactory()
        self.throttle = SubmissionURLThrottle()

    def test_requests_are_not_throttled_for_get(self):
        request = self.factory.get("/bob/submission")
        key = self.throttle.get_cache_key(request, None)
        self.assertEqual(key, None)

    def test_requests_are_not_throttled_for_non_submission_urls(self):
        request = self.factory.post("/projects/")
        key = self.throttle.get_cache_key(request, None)
        self.assertEqual(key, None)

    def test_requests_are_throttled(self):
        request = self.factory.post("/bob/submission")
        key = self.throttle.get_cache_key(request, None)
        self.assertEqual(key, 'throttle_method_POST_path_/bob/submission')

        request = self.factory.post("/project/124/submission")
        key = self.throttle.get_cache_key(request, None)
        self.assertEqual(key, 'throttle_method_POST_path_/project/124/submission')


class RequestHeaderThrottlingTests(TestCase):
    """
    Test Renderer class.
    """

    def setUp(self):
        """
        Reset the cache so that no throttles will be active
        """
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
