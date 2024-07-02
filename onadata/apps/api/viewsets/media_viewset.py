# -*- coding: utf-8 -*-
"""
The /api/v1/media API implementation.

List, Create, Update, Delete MetaData objects.
"""
from django.conf import settings
from django.http import Http404
from django.http import HttpResponseRedirect

from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.exceptions import ParseError

from onadata.apps.api.permissions import AttachmentObjectPermissions
from onadata.apps.logger.models import Attachment
from onadata.libs import filters
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.utils.image_tools import image_url, generate_media_download_url
from onadata.apps.api.tools import get_baseviewset_class

BaseViewset = get_baseviewset_class()


# pylint: disable=too-many-ancestors
class MediaViewSet(
    AuthenticateHeaderMixin,
    CacheControlMixin,
    ETagsMixin,
    BaseViewset,
    viewsets.ReadOnlyModelViewSet,
):
    """A view to redirect to actual attachments url"""

    queryset = Attachment.objects.filter(deleted_at__isnull=True)
    filter_backends = (filters.AttachmentFilter, filters.AttachmentTypeFilter)
    lookup_field = "pk"
    permission_classes = (AttachmentObjectPermissions,)

    # pylint: disable=invalid-name
    def retrieve(self, request, *args, **kwargs):
        """
        Redirect to final attachment url

        param pk: the attachment id
        query param filename: the filename of the attachment is required and must match
        query param suffix: (optional) - specify small | medium | large to
                            return resized images.

        return HttpResponseRedirect: redirects to final image url
        """
        pk = kwargs.get("pk")
        try:
            int(pk)
        except ValueError as exc:
            raise Http404() from exc
        filename = request.query_params.get("filename")
        obj = self.get_object()

        if obj.media_file.name != filename:
            raise Http404()

        url = None

        if obj.mimetype.startswith("image"):
            suffix = request.query_params.get("suffix")

            if suffix:
                if suffix in list(settings.THUMB_CONF):
                    try:
                        url = image_url(obj, suffix)
                    except Exception as e:
                        raise ParseError(e) from e
                else:
                    raise Http404()

        if not url:
            response = generate_media_download_url(obj)

            return response

        return HttpResponseRedirect(url)

    def list(self, request, *args, **kwargs):
        """
        Action NOT IMPLEMENTED.
        It is only needed because of the automatic URL routing in /api/v1/
        """
        return Response(data=[])
