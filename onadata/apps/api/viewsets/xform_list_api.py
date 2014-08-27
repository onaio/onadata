import pytz

from datetime import datetime
from django.conf import settings
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.decorators import action

from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs import filters
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.renderers.renderers import XFormListRenderer
from onadata.libs.renderers.renderers import XFormManifestRenderer
from onadata.libs.serializers.xform_serializer import XFormListSerializer
from onadata.libs.serializers.xform_serializer import XFormManifestSerializer


# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, 'DEFAULT_CONTENT_LENGTH', 10000000)


class XFormListApi(viewsets.ReadOnlyModelViewSet):
    authentication_classes = (DigestAuthentication,)
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    model = XForm
    permission_classes = (permissions.IsAuthenticated,)
    renderer_classes = (XFormListRenderer,)
    serializer_class = XFormListSerializer
    template_name = 'api/xformsList.xml'

    def get_openrosa_headers(self):
        tz = pytz.timezone(settings.TIME_ZONE)
        dt = datetime.now(tz).strftime('%a, %d %b %Y %H:%M:%S %Z')

        return {
            'Date': dt,
            'X-OpenRosa-Version': '1.0',
            'X-OpenRosa-Accept-Content-Length': DEFAULT_CONTENT_LENGTH
        }

    def get_renderers(self):
        if self.action and self.action == 'manifest':
            return [XFormManifestRenderer()]

        return super(XFormListApi, self).get_renderers()

    def list(self, request, *args, **kwargs):
        self.object_list = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(self.object_list, many=True)

        return Response(serializer.data, headers=self.get_openrosa_headers())

    def retrieve(self, request, *args, **kwargs):
        self.object = self.get_object()

        return Response(self.object.xml, headers=self.get_openrosa_headers())

    @action(methods=['GET'])
    def manifest(self, request, *args, **kwargs):
        self.object = self.get_object()
        object_list = MetaData.objects.filter(data_type='media')
        context = self.get_serializer_context()
        serializer = XFormManifestSerializer(object_list, many=True,
                                             context=context)

        return Response(serializer.data, headers=self.get_openrosa_headers())
