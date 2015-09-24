from django.conf import settings
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404

from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from onadata.apps.logger.models import Attachment
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.utils.image_tools import image_url
from onadata.apps.api.tools import get_baseviewset_class

BaseViewset = get_baseviewset_class()


class MediaViewSet(AuthenticateHeaderMixin,
                   CacheControlMixin, ETagsMixin, BaseViewset,
                   viewsets.ViewSet):
    """A view to redirect to actual attachments url"""
    permission_classes = (AllowAny, )

    def retrieve(self, request, pk=None):
        """
        Redirect to final attachment url

        param pk: the attachment id
        query param filename: the filename of the associated attachment is
            required and has to match
        query param suffix: (optional) - specify small | medium | large to
            return resized images.

        return HttpResponseRedirect: redirects to final image url
        """
        try:
            int(pk)
        except ValueError:
            raise Http404()
        else:
            filename = request.QUERY_PARAMS.get('filename')
            attachments = Attachment.objects.all()
            obj = get_object_or_404(attachments, pk=pk)

            if obj.media_file.name != filename:
                raise Http404()

            url = None

            if obj.mimetype.startswith('image'):
                suffix = request.QUERY_PARAMS.get('suffix')

                if suffix:
                    if suffix in settings.THUMB_CONF.keys():
                        url = image_url(obj, suffix)
                    else:
                        raise Http404()

            if not url:
                url = obj.media_file.url

            return HttpResponseRedirect(url)

        raise Http404()

    def list(self, request, *args, **kwargs):
        """
            Action NOT IMPLEMENTED, only needed because of the automatic url
            routing in /api/v1/
        """
        return Response(data=[])
