from rest_framework import renderers
from rest_framework import viewsets
from rest_framework.response import Response

from onadata.apps.api.permissions import MetaDataProjectObjectPermissions
from onadata.apps.api.tools import get_media_file_response
from onadata.apps.main.models.meta_data import ProjectMetaData
from onadata.libs.serializers.metadata_serializer import (
    ProjectMetaDataSerializer)
from onadata.libs import filters
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.renderers.renderers import MediaFileContentNegotiation, \
    MediaFileRenderer
from onadata.apps.api.tools import get_baseviewset_class

BaseViewset = get_baseviewset_class()


class ProjectMetaDataViewSet(AuthenticateHeaderMixin,
                             CacheControlMixin,
                             ETagsMixin,
                             BaseViewset,
                             viewsets.ModelViewSet):
    """
    This endpoint provides access to form metadata.
    """

    content_negotiation_class = MediaFileContentNegotiation
    filter_backends = (filters.MetaDataFilter,)
    queryset = ProjectMetaData.objects.all()
    permission_classes = (MetaDataProjectObjectPermissions,)
    renderer_classes = (
        renderers.JSONRenderer,
        renderers.BrowsableAPIRenderer,
        MediaFileRenderer)
    serializer_class = ProjectMetaDataSerializer

    def retrieve(self, request, *args, **kwargs):
        self.object = self.get_object()

        if isinstance(request.accepted_renderer, MediaFileRenderer) \
                and self.object.data_file is not None:

            return get_media_file_response(self.object)

        serializer = self.get_serializer(self.object)

        return Response(serializer.data)
