from django.conf import settings


CACHE_MIXIN_SECONDS = 60


class CacheControlMixin(object):

    def finalize_response(self, request, response, *args, **kwargs):
        if request.method == 'GET' and not response.streaming and \
                response.status_code in [200, 201, 202]:
            max_age = CACHE_MIXIN_SECONDS

            if hasattr(settings, 'CACHE_MIXIN_SECONDS'):
                max_age = settings.CACHE_MIXIN_SECONDS

            self.headers.update({'Cache-Control': max_age})

        return super(CacheControlMixin, self).finalize_response(
            request, response, *args, **kwargs)
