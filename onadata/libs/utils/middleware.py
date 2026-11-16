# -*- coding: utf-8 -*-
"""
Custom middleware classes.
"""

import logging
import traceback
from sys import stdout

from django.db import DatabaseError, OperationalError, connection
from django.http import HttpResponseNotAllowed
from django.middleware.locale import LocaleMiddleware
from django.template import loader
from django.utils.translation import gettext as _
from django.utils.translation.trans_real import parse_accept_lang_header

import sentry_sdk
from multidb.pinning import pin_this_thread, this_thread_is_pinned, unpin_this_thread

from onadata.apps.main.models.user_activity import record_user_activity

logger = logging.getLogger(__name__)


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


class ActivityTrackingMiddleware:  # pylint: disable=too-few-public-methods
    """Record activity for requests that authenticated by any middleware or view."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)

        if getattr(user, "is_authenticated", False):
            try:
                record_user_activity(user)
            except DatabaseError:
                logger.exception("Failed to record user activity for user %s", user.pk)

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


RECOVERY_CONFLICT_MESSAGE = "canceling statement due to conflict with recovery"
RECOVERY_CONFLICT_RETRY_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _noop():
    pass


def _call_after_reading(content, callback):
    """Yield ``content``, then call ``callback`` when reading finishes or stops.

    Reading a streamed response can run more queries, so a pin taken for the
    response has to last until then.
    """
    try:
        yield from content
    finally:
        callback()


# pylint: disable=too-few-public-methods
class OperationalErrorMiddleware(BaseMiddleware):
    """
    Retries a read request once on the primary database when a replica
    cancels one of its queries because of a recovery conflict.
    """

    def process_exception(self, request, exception):
        """Re-run the request with reads pinned to the primary database."""
        if not self._should_retry(request, exception):
            return None

        request.recovery_conflict_retried = True
        return self._retry_on_primary(request, exception)

    @staticmethod
    def _report_retry(request, exception):
        # Django doesn't report an exception that process_exception handles.
        # Report it here so retries stay measurable.
        logger.warning(
            "Retrying %s %s on the primary after a replica recovery conflict",
            request.method,
            request.path,
        )
        sentry_sdk.capture_exception(exception, level="info")

    def _retry_on_primary(self, request, exception):
        # Not ``use_master``: it keeps a single saved pin state per thread, so
        # a ``use_master`` block inside the retried view would leave the
        # thread pinned to the primary after the retry.
        restore_pin = _noop if this_thread_is_pinned() else unpin_this_thread
        pin_this_thread()
        try:
            # Pinned first: reporting can query, through reprs of locals.
            self._report_retry(request, exception)
            response = self.get_response(request)
        except BaseException:
            restore_pin()
            raise

        if response.streaming:
            response.streaming_content = _call_after_reading(
                response.streaming_content, restore_pin
            )
        else:
            restore_pin()
        return response

    @staticmethod
    def _should_retry(request, exception):
        return (
            isinstance(exception, OperationalError)
            and RECOVERY_CONFLICT_MESSAGE in str(exception)
            and request.method in RECOVERY_CONFLICT_RETRY_METHODS
            and not getattr(request, "recovery_conflict_retried", False)
        )
