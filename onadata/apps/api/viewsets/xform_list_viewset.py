import pytz

from datetime import datetime

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.decorators import action

from onadata.apps.api.tools import get_media_file_response
from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs import filters
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.authentication import EnketoTempTokenAuthentication
from onadata.libs.renderers.renderers import MediaFileContentNegotiation
from onadata.libs.renderers.renderers import XFormListRenderer
from onadata.libs.renderers.renderers import XFormManifestRenderer
from onadata.libs.serializers.xform_serializer import XFormListSerializer
from onadata.libs.serializers.xform_serializer import XFormManifestSerializer


# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, 'DEFAULT_CONTENT_LENGTH', 10000000)


class XFormListViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = (DigestAuthentication,
                              EnketoTempTokenAuthentication,)
    content_negotiation_class = MediaFileContentNegotiation
    filter_backends = (filters.XFormListObjectPermissionFilter,)
    queryset = XForm.objects.filter(downloadable=True, deleted_at=None)
    permission_classes = (permissions.AllowAny,)
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

        return super(XFormListViewSet, self).get_renderers()

    def filter_queryset(self, queryset):
        username = self.kwargs.get('username')
        if username is None and self.request.user.is_anonymous():
            # raises a permission denied exception, forces authentication
            self.permission_denied(self.request)

        if username is not None:
            profile = get_object_or_404(
                UserProfile, user__username=username.lower())

            if profile.require_auth and self.request.user.is_anonymous():
                # raises a permission denied exception, forces authentication
                self.permission_denied(self.request)
            else:
                queryset = queryset.filter(user=profile.user)

        if not self.request.user.is_anonymous():
            queryset = super(XFormListViewSet, self).filter_queryset(queryset)

        return queryset

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
        object_list = MetaData.objects.filter(data_type='media',
                                              xform=self.object)
        context = self.get_serializer_context()
        serializer = XFormManifestSerializer(object_list, many=True,
                                             context=context)

        return Response(serializer.data, headers=self.get_openrosa_headers())

    @action(methods=['GET'])
    def media(self, request, *args, **kwargs):
        self.object = self.get_object()
        pk = kwargs.get('metadata')

        if not pk:
            raise Http404()

        meta_obj = get_object_or_404(
            MetaData, data_type='media', xform=self.object, pk=pk)

        return get_media_file_response(meta_obj)
