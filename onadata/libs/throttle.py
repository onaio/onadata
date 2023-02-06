"""
Module containing throttling utilities
"""

from django.conf import Settings

from rest_framework.throttling import SimpleRateThrottle


class RequestHeaderThrottle(SimpleRateThrottle):
    """
    Custom Throttling class that throttles requests that match a specific
    header
    """

    scope = "header"
    throttled_headers = getattr(
        Settings,
        "THROTTLE_HEADERS",
        {"HTTP_USER_AGENT": "Google-HTTP-Java-Client/1.35.0 (gzip)"},
    )

    def get_cache_key(self, request, _):
        for header, value in self.throttled_headers.items():
            header_value = request.META.get(header, None)
            if header_value == value:
                ident = header_value
                # remove whitespace from key
                cleaned_ident = ident.replace(" ", "")
                return self.cache_format % {
                    "scope": self.scope,
                    "ident": cleaned_ident
                }
        return None
