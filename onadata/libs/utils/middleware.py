# -*- coding: utf-8 -*-
"""
Custom middleware classes.
"""
import logging
import traceback
from sys import stdout

from django.conf import settings
from django.db import OperationalError, connection
from django.http import HttpResponseNotAllowed
from django.middleware.locale import LocaleMiddleware
from django.template import loader
from django.utils.translation import gettext as _
from django.utils.translation.trans_real import parse_accept_lang_header

from multidb.pinning import use_master


class BaseMiddleware:  # pylint: disable=too-few-public-methods
    """BaseMiddleware - The base middleware class."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)


class ExceptionLoggingMiddleware:  # pylint: disable=too-few-public-methods
    """The exception logging middleware class - prints the exception traceback."""

    def __init__(self, get_response):
        self.get_response = get_response

    # pylint: disable=unused-argument
    def process_exception(self, request, exception):
        """Prints the exception traceback."""
        print(traceback.format_exc())


class HTTPResponseNotAllowedMiddleware:  # pylint: disable=too-few-public-methods
    """The HTTP Not Allowed middleware class - renders the 405.html template."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if isinstance(response, HttpResponseNotAllowed):
            response.content = loader.render_to_string("405.html", request=request)

        return response


class LocaleMiddlewareWithTweaks(LocaleMiddleware):
    """
    Overrides LocaleMiddleware from django with:
        Khmer `km` language code in Accept-Language is rewritten to km-kh
    """

    def process_request(self, request):
        accept = request.headers.get("Accept-Language", "")
        try:
            codes = [code for code, r in parse_accept_lang_header(accept)]
            if "km" in codes and "km-kh" not in codes:
                request.META["HTTP_ACCEPT_LANGUAGE"] = accept.replace("km", "km-kh")
        except Exception as error:  # pylint: disable=broad-except
            # this might fail if i18n is disabled.
            logging.exception(
                _(
                    "Settings request META HTTP accept language "
                    f"threw exceptions: {str(error)}"
                )
            )

        super().process_request(request)


class SqlLogging:  # pylint: disable=too-few-public-methods
    """
    SQL logging middleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if stdout.isatty():
            for query in connection.queries:
                time = query["time"]
                sql = " ".join(query["sql"].split())
                print(f"\033[1;31m[{time}]\033[0m \033[1m{sql}\033[0m")

        return response


# pylint: disable=too-few-public-methods
class OperationalErrorMiddleware(BaseMiddleware):
    """
    Captures requests returning 500 status code.
    Then retry it against master database.
    """

    def process_exception(self, request, exception):
        """
        Handle retrying OperatuonalError exceptions.
        """
        # Filter out OperationalError Exceptions
        if isinstance(exception, OperationalError):
            already_raised = getattr(settings, "ALREADY_RAISED", False)
            message = "canceling statement due to conflict with recovery"
            if message in str(exception):
                if not already_raised:
                    settings.ALREADY_RAISED = True
                    with use_master:
                        response = self.get_response(request)
                        return response
                settings.ALREADY_RAISED = False

        return None
