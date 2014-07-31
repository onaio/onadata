from rest_framework import negotiation, renderers, viewsets
from rest_framework.response import Response

from onadata.apps.api.permissions import MetaDataObjectPermissions
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer
from onadata.libs import filters


class MediaFileContentNegotiation(negotiation.DefaultContentNegotiation):
    def filter_renderers(self, renderers, format):
        """
        If there is a '.json' style format suffix, filter the renderers
        so that we only negotiation against those that accept that format.
        If there is no renderer available, we use MediaFileRenderer.
        """
        renderers = [renderer for renderer in renderers
                     if renderer.format == format]
        if not renderers:
            renderers = [MediaFileRenderer()]

        return renderers


class MediaFileRenderer(renderers.BaseRenderer):
    media_type = '*/*'
    format = None
    charset = None
    render_style = 'binary'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class MetaDataViewSet(viewsets.ModelViewSet):
    content_negotiation_class = MediaFileContentNegotiation
    filter_backends = (filters.MetaDataFilter,)
    model = MetaData
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
            data = self.object.data_file.read()

            return Response(data, content_type=self.object.data_file_type)

        serializer = self.get_serializer(self.object)

        return Response(serializer.data)
