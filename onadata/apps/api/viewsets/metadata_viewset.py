from rest_framework import renderers
from rest_framework import viewsets
from rest_framework.response import Response

from onadata.apps.api.permissions import MetaDataObjectPermissions
from onadata.apps.api.tools import get_media_file_response
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer
from onadata.libs import filters
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.renderers.renderers import MediaFileContentNegotiation, \
    MediaFileRenderer


class MetaDataViewSet(CacheControlMixin,
                      ETagsMixin,
                      viewsets.ModelViewSet):
    """
    This endpoint provides access to form metadata.
    """
    content_negotiation_class = MediaFileContentNegotiation
    filter_backends = (filters.MetaDataFilter,)
    queryset = MetaData.objects.select_related('xform')
    permission_classes = (MetaDataObjectPermissions,)
    renderer_classes = (
        renderers.JSONRenderer,
        renderers.BrowsableAPIRenderer,
        MediaFileRenderer)
    serializer_class = MetaDataSerializer

    def retrieve(self, request, *args, **kwargs):
        self.object = self.get_object()

        if isinstance(request.accepted_renderer, MediaFileRenderer) \
                and self.object.data_file is not None:

            return get_media_file_response(self.object)

        serializer = self.get_serializer(self.object)

        return Response(serializer.data)
