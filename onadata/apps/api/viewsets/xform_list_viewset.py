import pytz

from datetime import datetime

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache

from rest_framework import viewsets
from rest_framework import permissions
from rest_framework.decorators import detail_route
from rest_framework.response import Response

from onadata.apps.api.tools import get_media_file_response
from onadata.apps.logger.models.xform import XForm, get_forms_shared_with_user
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs import filters
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.authentication import EnketoTokenAuthentication
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.renderers.renderers import MediaFileContentNegotiation
from onadata.libs.renderers.renderers import XFormListRenderer
from onadata.libs.renderers.renderers import XFormManifestRenderer
from onadata.libs.serializers.xform_serializer import XFormListSerializer
from onadata.libs.serializers.xform_serializer import XFormManifestSerializer
from onadata.apps.api.tools import get_baseviewset_class
from onadata.libs.utils.export_tools import ExportBuilder
from onadata.libs.utils.common_tags import GROUP_DELIMETER_TAG


BaseViewset = get_baseviewset_class()


# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, 'DEFAULT_CONTENT_LENGTH', 10000000)


class XFormListViewSet(ETagsMixin, BaseViewset,
                       viewsets.ReadOnlyModelViewSet):
    authentication_classes = (DigestAuthentication,
                              EnketoTokenAuthentication,)
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

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {self.lookup_field: self.kwargs[self.lookup_field]}
        obj = get_object_or_404(queryset or XForm, **filter_kwargs)
        self.check_object_permissions(self.request, obj)

        return obj

    def get_renderers(self):
        if self.action and self.action == 'manifest':
            return [XFormManifestRenderer()]

        return super(XFormListViewSet, self).get_renderers()

    def filter_queryset(self, queryset):
        username = self.kwargs.get('username')
        if username is None and self.request.user.is_anonymous():
            # raises a permission denied exception, forces authentication
            self.permission_denied(self.request)

        profile = None
        if username is not None:
            profile = get_object_or_404(
                UserProfile, user__username=username.lower())

            if profile.require_auth and self.request.user.is_anonymous():
                # raises a permission denied exception, forces authentication
                self.permission_denied(self.request)
            else:
                queryset = queryset.filter(
                    user=profile.user, downloadable=True)

        if not self.request.user.is_anonymous():
            queryset = super(XFormListViewSet, self).filter_queryset(queryset)

            if self.action == 'list' and profile:
                forms_shared_with_user = get_forms_shared_with_user(
                    profile.user)
                queryset = queryset | forms_shared_with_user
                if self.request.user != profile.user:
                    public_forms = profile.user.xforms.filter(
                        downloadable=True, shared=True)
                    queryset = queryset | public_forms

        return queryset

    @never_cache
    def list(self, request, *args, **kwargs):
        self.object_list = self.filter_queryset(self.get_queryset())

        serializer = self.get_serializer(self.object_list, many=True)

        return Response(serializer.data, headers=self.get_openrosa_headers())

    def retrieve(self, request, *args, **kwargs):
        self.object = self.get_object()

        return Response(self.object.xml, headers=self.get_openrosa_headers())

    @detail_route(methods=['GET'])
    def manifest(self, request, *args, **kwargs):
        self.object = self.get_object()
        object_list = MetaData.objects.filter(data_type='media',
                                              object_id=self.object.pk)
        context = self.get_serializer_context()
        context[GROUP_DELIMETER_TAG] = ExportBuilder.GROUP_DELIMITER_DOT
        serializer = XFormManifestSerializer(object_list, many=True,
                                             context=context)

        return Response(serializer.data, headers=self.get_openrosa_headers())

    @detail_route(methods=['GET'])
    def media(self, request, *args, **kwargs):
        self.object = self.get_object()
        pk = kwargs.get('metadata')

        if not pk:
            raise Http404()

        meta_obj = get_object_or_404(
            MetaData, data_type='media', object_id=self.object.pk, pk=pk)
        response = get_media_file_response(meta_obj, request)

        if response.status_code == 403 and request.user.is_anonymous():
            # raises a permission denied exception, forces authentication
            self.permission_denied(request)
        else:
            return response


class PreviewXFormListViewSet(XFormListViewSet):
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    permission_classes = (permissions.AllowAny,)
