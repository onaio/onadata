from django.http import Http404
from django.utils.translation import ugettext as _
from rest_framework import renderers
from rest_framework import viewsets
from rest_framework.response import Response


from onadata.apps.api.permissions import AttachmentObjectPermissions
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.xform import XForm
from onadata.libs import filters
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
from onadata.libs.serializers.attachment_serializer import AttachmentSerializer
from onadata.libs.renderers.renderers import MediaFileContentNegotiation, \
    MediaFileRenderer


class AttachmentViewSet(LastModifiedMixin, viewsets.ReadOnlyModelViewSet):
    content_negotiation_class = MediaFileContentNegotiation
    filter_backends = (filters.AttachmentFilter,)
    lookup_field = 'pk'
    queryset = Attachment.objects.all()
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

        filename = request.QUERY_PARAMS.get('filename')
        serializer = self.get_serializer(self.object)

        if filename:
            if filename == self.object.media_file.name:
                return Response(serializer.get_download_url(self.object))
            else:
                raise Http404(_("Filename '%s' not found." % filename))

        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        if request.user.is_anonymous():
            xform = request.QUERY_PARAMS.get('xform')
            if xform:
                xform = XForm.objects.get(id=xform)
                if not xform.shared_data:
                    raise Http404(_("Not Found"))

        return super(AttachmentViewSet, self).list(request, *args, **kwargs)
