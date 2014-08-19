from rest_framework import viewsets


from onadata.apps.logger.models.attachment import Attachment
from onadata.libs.serializers.attachment_serializer import AttachmentSerializer


class AttachmentViewSet(viewsets.ReadOnlyModelViewSet):
    model = Attachment
    serializer_class = AttachmentSerializer
    lookup_field = 'pk'
