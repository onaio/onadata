"""
Request factory whose requests read headers from META on every access.
"""

from django.core.handlers.wsgi import WSGIRequest
from django.http.request import HttpHeaders

from rest_framework.test import APIRequestFactory


class LiveHeadersRequest(WSGIRequest):
    """A request whose ``headers`` always reflect the current ``META``."""

    @property
    def headers(self):  # pylint: disable=invalid-overridden-method
        return HttpHeaders(self.META)


class LiveHeadersRequestFactory(APIRequestFactory):
    """
    APIRequestFactory for tests that answer a 401 challenge by adding
    credentials to ``request.META`` and dispatching the same request again.

    Django caches ``request.headers`` on first access, and DRF reads the
    Authorization header through it, so credentials added afterwards would
    otherwise be ignored.
    """

    def request(self, **kwargs):
        request = super().request(**kwargs)
        request.__class__ = LiveHeadersRequest
        return request
