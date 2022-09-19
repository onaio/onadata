# -*- coding: utf-8 -*-
"""
The /api/v1/metadata API implementation.

List, Create, Update, Delete MetaData objects.
"""
from rest_framework import renderers
from rest_framework import viewsets
from rest_framework.response import Response

from onadata.apps.api.permissions import MetaDataObjectPermissions
from onadata.apps.api.tools import get_media_file_response
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer
from onadata.libs import filters
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.renderers.renderers import (
    MediaFileContentNegotiation,
    MediaFileRenderer,
)
from onadata.apps.api.tools import get_baseviewset_class


BaseViewset = get_baseviewset_class()


# pylint: disable=too-many-ancestors
class MetaDataViewSet(
    AuthenticateHeaderMixin,
    CacheControlMixin,
    ETagsMixin,
    BaseViewset,
    viewsets.ModelViewSet,
):
    """
    List, Create, Update, Delete MetaData objects.
    """

    content_negotiation_class = MediaFileContentNegotiation
    filter_backends = (filters.MetaDataFilter,)
    queryset = MetaData.objects.filter(deleted_at__isnull=True).select_related()
    permission_classes = (MetaDataObjectPermissions,)
    renderer_classes = (
        renderers.JSONRenderer,
        renderers.BrowsableAPIRenderer,
        MediaFileRenderer,
    )
    serializer_class = MetaDataSerializer

    def retrieve(self, request, *args, **kwargs):
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        if (
            isinstance(request.accepted_renderer, MediaFileRenderer)
            and self.object.data_file is not None
        ):

            return get_media_file_response(self.object, request)

        serializer = self.get_serializer(self.object)

        return Response(serializer.data)
