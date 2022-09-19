# -*- coding: utf-8 -*-
"""
Implements a ProfilerMixin - profiles a Django Rest Framework viewset.
"""
import logging
import time

from django.conf import settings
from django.core.signals import request_finished, request_started
from django.http import StreamingHttpResponse

from rest_framework.fields import empty

project_viewset_profiler = logging.getLogger("profiler_logger")

DISPATCH_TIME = 0
RENDER_TIME = 0
STARTED = 0
SERIALIZER_TIME = 0


class ProfilerMixin:
    """
    Implements a ProfilerMixin - profiles a Django Rest Framework viewset.
    """

    def get_serializer(self, instance=None, data=empty, **kwargs):
        """Override the get_serializer() method."""
        serializer_class = self.get_serializer_class()
        kwargs["context"] = self.get_serializer_context()

        if settings.PROFILE_API_ACTION_FUNCTION:
            global SERIALIZER_TIME  # pylint: disable=global-statement
            serializer_start = time.time()

            serializer = serializer_class(instance, data=data, **kwargs)
            SERIALIZER_TIME = time.time() - serializer_start
            return serializer

        return serializer_class(instance, data=data, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        """Override the viewset dispatch method."""
        global RENDER_TIME  # pylint: disable=global-statement
        global DISPATCH_TIME  # pylint: disable=global-statement

        dispatch_start = time.time()
        ret = super().dispatch(request, *args, **kwargs)

        if not isinstance(ret, StreamingHttpResponse):
            render_start = time.time()
            ret.render()
            RENDER_TIME = time.time() - render_start
        else:
            RENDER_TIME = 0
        DISPATCH_TIME = time.time() - dispatch_start

        return ret


def started(sender, **kwargs):  # pylint: disable=unused-argument
    """Signal that starts the timer"""
    global STARTED  # pylint: disable=global-statement
    STARTED = time.time()


def finished(sender, **kwargs):  # pylint: disable=unused-argument
    """Signal that captures the end of the timer"""
    try:
        total = time.time() - STARTED
        api_view_time = dispatch_time - (render_time + serializer_time)
        request_response_time = total - dispatch_time

        # pylint: disable=consider-using-f-string
        output = "\n"
        output += "Serialization                 | %.4fs\n" % serializer_time
        output += "Django request/response       | %.4fs\n" % request_response_time
        output += "API view                      | %.4fs\n" % api_view_time
        output += "Response rendering            | %.4fs\n" % render_time

        project_viewset_profiler.debug(output)

    except NameError:
        pass


if settings.PROFILE_API_ACTION_FUNCTION:
    request_started.connect(started)
    request_finished.connect(finished)
