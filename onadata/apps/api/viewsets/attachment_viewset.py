# -*- coding: utf-8 -*-
"""
The /api/v1/attachments API implementation.
"""

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from rest_framework import renderers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.response import Response

from onadata.apps.api.permissions import AttachmentObjectPermissions
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.xform import XForm
from onadata.libs import filters
from onadata.libs.data import parse_int
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.renderers.renderers import (
    MediaFileContentNegotiation,
    MediaFileRenderer,
)
from onadata.libs.serializers.attachment_serializer import AttachmentSerializer
from onadata.libs.utils.image_tools import image_url
from onadata.libs.utils.viewer_tools import get_path


def get_attachment_data(attachment, suffix):
    """Returns attachment file contents."""
    if suffix in list(settings.THUMB_CONF):
        image_url(attachment, suffix)
        suffix = settings.THUMB_CONF.get(suffix).get("suffix")
        media_file = default_storage.open(get_path(attachment.media_file.name, suffix))
        return media_file.read()

    return attachment.media_file.read()


# pylint: disable=too-many-ancestors
class AttachmentViewSet(
    AuthenticateHeaderMixin,
    CacheControlMixin,
    ETagsMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """
    GET, List attachments implementation.
    """

    content_negotiation_class = MediaFileContentNegotiation
    filter_backends = (filters.AttachmentFilter, filters.AttachmentTypeFilter)
    lookup_field = "pk"
    queryset = Attachment.objects.filter(
        instance__deleted_at__isnull=True, deleted_at__isnull=True
    )
    permission_classes = (AttachmentObjectPermissions,)
    serializer_class = AttachmentSerializer
    pagination_class = StandardPageNumberPagination
    renderer_classes = (
        renderers.JSONRenderer,
        renderers.BrowsableAPIRenderer,
        MediaFileRenderer,
    )

    def retrieve(self, request, *args, **kwargs):
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()

        if (
            isinstance(request.accepted_renderer, MediaFileRenderer)
            and self.object.media_file is not None
        ):
            suffix = request.query_params.get("suffix")
            try:
                data = get_attachment_data(self.object, suffix)
            except IOError as error:
                if str(error).startswith("File does not exist"):
                    raise Http404() from error

                raise ParseError(error) from error
            return Response(data, content_type=self.object.mimetype)

        filename = request.query_params.get("filename")
        serializer = self.get_serializer(self.object)

        if filename:
            if filename == self.object.media_file.name:
                return Response(serializer.get_download_url(self.object))

            raise Http404(_(f"Filename '{filename}' not found."))

        return Response(serializer.data)

    @action(methods=["GET"], detail=False)
    def count(self, request, *args, **kwargs):
        """Returns the number of attachments the user has access to."""
        data = {"count": self.filter_queryset(self.get_queryset()).count()}

        return Response(data=data)

    def list(self, request, *args, **kwargs):
        if request.user.is_anonymous:
            xform = request.query_params.get("xform")
            if xform:
                xform = parse_int(xform)
                if xform:
                    xform = get_object_or_404(XForm, pk=xform)
                    if not xform.shared_data:
                        raise Http404(_("Not Found"))
                else:
                    raise Http404(_("Not Found"))

        # pylint: disable=attribute-defined-outside-init
        self.object_list = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(self.object_list.order_by("pk"))
        if page is not None:
            serializer = self.get_serializer(page, many=True)

            return Response(serializer.data)

        return super().list(request, *args, **kwargs)
