# -*- coding: utf-8 -*-
"""
Implements the CacheControlMixin class

Adds Cache headers to a viewsets response.
"""
from django.conf import settings
from django.utils.cache import patch_cache_control


CACHE_CONTROL_VALUE = "max-age=60"


def set_cache_control(response, cache_control_value=CACHE_CONTROL_VALUE):
    pragma = None
    if hasattr(settings, 'CACHE_CONTROL_VALUE'):
        cache_control_value = settings.CACHE_CONTROL_VALUE
    if hasattr(settings, 'PRAGMA_VALUE'):
        pragma = settings.PRAGMA_VALUE
    response['Cache-Control'] = cache_control_value
    if pragma:
        response['Pragma'] = pragma
    return response


class CacheControlMixin(object):
    def finalize_response(self, request, response, *args, **kwargs):
        if request.method == 'GET' and not response.streaming and \
                response.status_code in [200, 201, 202]:
            response = set_cache_control(response)

        return super(CacheControlMixin, self).finalize_response(
            request, response, *args, **kwargs)


class CacheControlMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return set_cache_control(response)
