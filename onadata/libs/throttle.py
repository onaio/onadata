"""
Module containing throttling utilities
"""

from django.conf import settings

from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle


class CustomScopedRateThrottle(ScopedRateThrottle):
    """
    Custom throttling for fair throttling for anonymous users sharing IP
    """

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return super().get_cache_key(request, view)

        return f"throttle_{self.scope}_{request.path}_{self.get_ident(request)}"


class UserIDThrottle(SimpleRateThrottle):
    """
    Custom Throttling class that throttles requests based on user ID for
    authenticated users. Anonymous users are throttled by IP address.
    """

    scope = "user"

    def get_rate(self):
        """
        Override to provide a default rate or get from settings
        """
        try:
            return super().get_rate()
        except KeyError:
            # Default rate if not configured
            return "100/minute"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            # Throttle authenticated users by user ID
            ident = request.user.id
            return self.cache_format % {"scope": self.scope, "ident": ident}
        else:
            # No throttling for anonymous users
            return None


class RequestHeaderThrottle(SimpleRateThrottle):
    """
    Custom Throttling class that throttles requests that match a specific
    header
    """

    scope = "header"

    @property
    def throttled_headers(self):
        return getattr(
            settings,
            "THROTTLE_HEADERS",
            {"HTTP_USER_AGENT": "Google-HTTP-Java-Client/1.35.0 (gzip)"},
        )

    def get_ident_from_header(self, value):
        cleaned_ident = value.replace(" ", "")
        return self.cache_format % {"scope": self.scope, "ident": cleaned_ident}

    def get_cache_key(self, request, _):
        for header, value in self.throttled_headers.items():
            header_value = request.META.get(header, None)
            if isinstance(value, str):
                if header_value == value:
                    return self.get_ident_from_header(header_value)
            elif isinstance(value, list):
                for val in value:
                    if header_value == val:
                        return self.get_ident_from_header(header_value)
        return None
