# -*- coding: utf-8 -*-
"""Custom Expecting classes."""
from django.utils.translation import gettext_lazy as _

from rest_framework.exceptions import APIException


class EnketoError(Exception):
    """Enketo specigic exceptions"""

    default_message = _(
        "There was a problem with your submission or form. Please contact support."
    )

    def __init__(self, message=None):
        self.message = message if message is not None else self.default_message
        super().__init__(self.message)


class NoRecordsFoundError(Exception):
    """Raise for when no records are found."""


class NoRecordsPermission(Exception):
    """Raise when no permissions to access records."""


class J2XException(Exception):
    """Raise for json-to-xls exceptions on external exports."""


class ServiceUnavailable(APIException):
    """Custom service unavailable exception."""

    status_code = 503
    default_detail = "Service temporarily unavailable, try again later."
