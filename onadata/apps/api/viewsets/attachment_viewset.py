from rest_framework import viewsets


from onadata.apps.api.permissions import AttachmentObjectPermissions
from onadata.apps.logger.models.attachment import Attachment
from onadata.libs import filters
from onadata.libs.serializers.attachment_serializer import AttachmentSerializer


class AttachmentViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = (filters.AttachmentFilter,)
    lookup_field = 'pk'
    model = Attachment
    permission_classes = (AttachmentObjectPermissions,)
    serializer_class = AttachmentSerializer
