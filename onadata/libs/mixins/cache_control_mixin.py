# -*- coding: utf-8 -*-
"""
Implements the CacheControlMixin class

Adds Cache headers to a viewsets response.
"""
from django.conf import settings
from django.utils.cache import patch_cache_control


CACHE_CONTROL_VALUE = {"max_age": 60}


def set_cache_control(response, cache_control_value=CACHE_CONTROL_VALUE):
    """
    Sets the `Cache-Control` headers on a `Response`
    Object
    """
    patch_cache_control(response, **CACHE_CONTROL_VALUE)
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
    Django Middleware used to set `Cache-Control` and `Pragma`
    headers for every response
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return set_cache_control(response)
