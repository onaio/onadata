# -*- coding=utf-8 -*-
"""
Implements the CacheControlMixin class

Adds Cache headers to a viewsets response.
"""
from django.conf import settings
from django.utils.cache import patch_cache_control

CACHE_MIXIN_SECONDS = 60


class CacheControlMixin:
    """
    Implements the CacheControlMixin class

    Adds Cache headers to a viewsets response.
    """

    def set_cache_control(self, response, max_age=CACHE_MIXIN_SECONDS):
        """Adds Cache headers to a response"""
        if hasattr(settings, "CACHE_MIXIN_SECONDS"):
            max_age = settings.CACHE_MIXIN_SECONDS

        patch_cache_control(response, max_age=max_age)

    def finalize_response(self, request, response, *args, **kwargs):
        """Overrides the finalize_response method

        Adds Cache headers to a response."""
        if (
            request.method == "GET"
            and not response.streaming
            and response.status_code in [200, 201, 202]
        ):
            self.set_cache_control(response)

        return super().finalize_response(request, response, *args, **kwargs)
