"""
Module containing throttling utilities
"""

from django.conf import settings

from rest_framework.throttling import SimpleRateThrottle


class SubmissionURLThrottle(SimpleRateThrottle):

    @property
    def rate(self):
        return getattr(
            settings,
            "THROTTLE_USERS_RATE",
            "40/min"
        )

    def get_form_owner_or_project_from_url(self, url):
        path_segments = url.split("/")
        if len(path_segments) > 1:
            return path_segments[-2]
        return None

    def get_cache_key(self, request, _):
        request_methods_to_throttle = getattr(
            settings,
            "SUBMISSION_REQUEST_METHODS_TO_THROTTLE",
            ['POST']
        )
        if (request.method in request_methods_to_throttle
                and '/submission' in request.path
                and self.get_form_owner_or_project_from_url(request.path)):
            return f"throttle_method_{request.method}_path_{request.path}"
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
