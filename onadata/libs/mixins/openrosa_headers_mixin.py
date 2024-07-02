# -*- coding: utf-8 -*-
"""
OpenRosaHeadersMixin module
"""
from django.conf import settings
from django.utils import timezone

# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, "DEFAULT_CONTENT_LENGTH", 10000000)


def get_openrosa_headers(request, location=True):
    """
    Returns a dict with OpenRosa headers 'Date', 'X-OpenRosa-Version',
    'X-OpenRosa-Accept-Content-Length' and 'Location'.
    """
    now = timezone.localtime()
    data = {
        "Date": now.strftime("%a, %d %b %Y %H:%M:%S %Z"),
        "X-OpenRosa-Version": "1.0",
        "X-OpenRosa-Accept-Content-Length": DEFAULT_CONTENT_LENGTH,
    }

    if location:
        data["Location"] = request.build_absolute_uri(request.path)

    return data


class OpenRosaHeadersMixin:  # pylint: disable=too-few-public-methods
    """
    OpenRosaHeadersMixin class - sets OpenRosa headers in a response for a View
    or Viewset.
    """

    def finalize_response(self, request, response, *args, **kwargs):
        """
        Adds OpenRosa headers into the response.
        """
        self.headers.update(get_openrosa_headers(request))

        return super().finalize_response(request, response, *args, **kwargs)
