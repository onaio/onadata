# -*- coding=utf-8 -*-
"""
OpenRosaHeadersMixin module
"""
from datetime import datetime

import pytz
from django.conf import settings

# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, 'DEFAULT_CONTENT_LENGTH', 10000000)


def get_openrosa_headers(request, location=True):
    """
    Returns a dict with OpenRosa headers 'Date', 'X-OpenRosa-Version',
    'X-OpenRosa-Accept-Content-Length' and 'Location'.
    """
    now = datetime.now(pytz.timezone(settings.TIME_ZONE))
    data = {
        'Date': now.strftime('%a, %d %b %Y %H:%M:%S %Z'),
        'X-OpenRosa-Version': '1.0',
        'X-OpenRosa-Accept-Content-Length': DEFAULT_CONTENT_LENGTH
    }

    if location:
        data['Location'] = request.build_absolute_uri(request.path)

    return data


class OpenRosaHeadersMixin(object):  # pylint: disable=R0903
    """
    OpenRosaHeadersMixin class - sets OpenRosa headers in a response for a View
    or Viewset.
    """

    def finalize_response(self, request, response, *args, **kwargs):
        """
        Adds OpenRosa headers into the response.
        """
        self.headers.update(get_openrosa_headers(request))

        return super(OpenRosaHeadersMixin, self).finalize_response(
            request, response, *args, **kwargs)
