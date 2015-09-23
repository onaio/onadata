import logging
import time
from django.conf import settings
from django.core.signals import request_started, request_finished


project_viewset_profiler = logging.getLogger('profiler_logger')


class ProfilerMixin(object):
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

    def get_list_serialization_time(self, **kwargs):
        if hasattr(self, 'get_serializer') and hasattr(self, 'object_list'):
            global serializer_time
            serializer_start = time.time()
            serializer = self.get_serializer(self.object_list, **kwargs)
            serializer_time = time.time() - serializer_start
            return serializer


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
