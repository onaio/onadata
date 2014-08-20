from rest_framework import renderers
from rest_framework import viewsets
from rest_framework.response import Response


from onadata.apps.api.permissions import AttachmentObjectPermissions
from onadata.apps.logger.models.attachment import Attachment
from onadata.libs import filters
from onadata.libs.serializers.attachment_serializer import AttachmentSerializer
from onadata.libs.renderers.renderers import MediaFileContentNegotiation, \
    MediaFileRenderer


class AttachmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ### This endpoint allows you to list and retrieve attachments
    <pre class="prettyprint">
    <b>GET</b> /api/v1/media</pre>

    > Example
    >
    >       curl -X GET https://ona.io/api/v1/media

    > Response
    >
    >        [{
    >            "url":
    >            "id":
    >            "xform":
    >            "data_id":
    >            "mimetype":
    >            "filename":
    >        }
    >        ...
    """
    content_negotiation_class = MediaFileContentNegotiation
    filter_backends = (filters.AttachmentFilter,)
    lookup_field = 'pk'
    model = Attachment
    permission_classes = (AttachmentObjectPermissions,)
    serializer_class = AttachmentSerializer
    renderer_classes = (
        renderers.JSONRenderer,
        renderers.BrowsableAPIRenderer,
        MediaFileRenderer)

    def retrieve(self, request, *args, **kwargs):
        self.object = self.get_object()

        if isinstance(request.accepted_renderer, MediaFileRenderer) \
                and self.object.media_file is not None:
            data = self.object.media_file.read()

            return Response(data, content_type=self.object.mimetype)

        serializer = self.get_serializer(self.object)

        return Response(serializer.data)
