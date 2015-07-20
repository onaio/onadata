from django.http import Http404
from django.utils.translation import ugettext as _
from django.core.files.storage import default_storage
from django.conf import settings
from rest_framework import renderers
from rest_framework import viewsets
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.pagination import BasePaginationSerializer

from onadata.apps.api.permissions import AttachmentObjectPermissions
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.xform import XForm
from onadata.libs import filters
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.serializers.attachment_serializer import AttachmentSerializer
from onadata.libs.renderers.renderers import MediaFileContentNegotiation, \
    MediaFileRenderer
from onadata.libs.utils.image_tools import image_url
from onadata.libs.utils.viewer_tools import get_path


def get_attachment_data(attachment, suffix):
    if suffix in settings.THUMB_CONF.keys():
        image_url(attachment, suffix)
        suffix = settings.THUMB_CONF.get(suffix).get('suffix')
        f = default_storage.open(
            get_path(attachment.media_file.name, suffix))
        data = f.read()
    else:
        data = attachment.media_file.read()

    return data


class AttachmentViewSet(AuthenticateHeaderMixin, CacheControlMixin, ETagsMixin,
                        viewsets.ReadOnlyModelViewSet):
    """
    List attachments of viewsets.
    """
    content_negotiation_class = MediaFileContentNegotiation
    filter_backends = (filters.AttachmentFilter,)
    lookup_field = 'pk'
    queryset = Attachment.objects.all()
    permission_classes = (AttachmentObjectPermissions,)
    serializer_class = AttachmentSerializer
    pagination_class = BasePaginationSerializer
    paginate_by_param = 'page_size'
    page_kwarg = 'page'
    renderer_classes = (
        renderers.JSONRenderer,
        renderers.BrowsableAPIRenderer,
        MediaFileRenderer)

    def retrieve(self, request, *args, **kwargs):
        self.object = self.get_object()

        if isinstance(request.accepted_renderer, MediaFileRenderer) \
                and self.object.media_file is not None:
            suffix = request.QUERY_PARAMS.get('suffix')
            try:
                data = get_attachment_data(self.object, suffix)
            except IOError as e:
                if unicode(e).startswith('File does not exist'):
                    raise Http404()

                raise ParseError(e)
            else:
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

        self.object_list = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(self.object_list)
        if page is not None:
            serializer = self.get_pagination_serializer(page)
            return Response(serializer.data.get('results'))

        return super(AttachmentViewSet, self).list(request, *args, **kwargs)
