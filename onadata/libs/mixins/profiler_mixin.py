import logging
import time
from django.conf import settings
from django.core.signals import request_started, request_finished


project_viewset_profiler = logging.getLogger('profiler_logger')


class ProfilerMixin(object):

    def get_serializer(self, instance=None, data=None, files=None, many=False,
                       partial=False, allow_add_remove=False):
        serializer_class = self.get_serializer_class()
        context = self.get_serializer_context()

        if settings.PROFILE_API_ACTION_FUNCTION:
            global serializer_time
            serializer_start = time.time()

            serializer = serializer_class(
                instance, data=data, files=files, many=many, partial=partial,
                allow_add_remove=allow_add_remove, context=context)
            serializer_time = time.time() - serializer_start
            return serializer

        return serializer_class(
            instance, data=data, files=files, many=many, partial=partial,
            allow_add_remove=allow_add_remove, context=context)

    def dispatch(self, request, *args, **kwargs):
        global render_time
        global dispatch_time

        dispatch_start = time.time()
        ret = super(ProfilerMixin, self).dispatch(request, *args, **kwargs)

        render_start = time.time()
        ret.render()
        render_time = time.time() - render_start

        dispatch_time = time.time() - dispatch_start

        return ret


def started(sender, **kwargs):
    global started
    started = time.time()


def finished(sender, **kwargs):
    try:
        total = time.time() - started
        api_view_time = dispatch_time - (render_time + serializer_time)
        request_response_time = total - dispatch_time

        output = "\n"
        output += "Serialization                 | %.4fs\n" % serializer_time
        output += "Django request/response       | %.4fs\n" %\
            request_response_time
        output += "API view                      | %.4fs\n" % api_view_time
        output += "Response rendering            | %.4fs\n" % render_time

        project_viewset_profiler.debug(output)

    except NameError:
        pass

if settings.PROFILE_API_ACTION_FUNCTION:
    request_started.connect(started)
    request_finished.connect(finished)
