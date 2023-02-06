from django.core.cache import cache
from django.test import TestCase, override_settings

from rest_framework.test import APIRequestFactory

from onadata.libs.throttle import RequestHeaderThrottle


class ThrottlingTests(TestCase):
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
