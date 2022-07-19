# -*- coding: utf-8 -*-
"""
Implements the CacheControlMixin class

Adds Cache headers to a viewsets response.
"""
from typing import Optional

from django.conf import settings
from django.utils.cache import patch_cache_control


def set_cache_control(response, cache_control_directives: Optional[dict] = None):
    """
    Sets the `Cache-Control` headers on a `Response`
    Object
    """
    cache_control_directives = {"max_age": 60}
    if hasattr(settings, 'CACHE_CONTROL_DIRECTIVES'):
        cache_control_directives = settings.CACHE_CONTROL_DIRECTIVES

    patch_cache_control(response, **cache_control_directives)
    return response


class CacheControlMixin(object):
    def finalize_response(self, request, response, *args, **kwargs):
        if (
            request.method == "GET"
            and not response.streaming
            and response.status_code in [200, 201, 202]
        ):
            response = set_cache_control(response)

        return super(CacheControlMixin, self).finalize_response(
            request, response, *args, **kwargs
        )


class CacheControlMiddleware:
    """
    Django Middleware used to set `Cache-Control`
    header for every response
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return set_cache_control(response)
