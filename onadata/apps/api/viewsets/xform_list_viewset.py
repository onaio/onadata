# -*- coding: utf-8 -*-
"""
OpenRosa Form List API - https://docs.getodk.org/openrosa-form-list/
"""

from django.conf import settings
from django.http import Http404, StreamingHttpResponse
from django.shortcuts import get_object_or_404

from django_filters import rest_framework as django_filter_filters
from rest_framework import permissions, viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.response import Response

from onadata.apps.api.tools import (
    get_baseviewset_class,
    get_media_file_response,
    get_xform_list_cache_key,
)
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import XForm, get_forms_shared_with_user
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs import filters
from onadata.libs.authentication import DigestAuthentication, EnketoTokenAuthentication
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.openrosa_headers_mixin import get_openrosa_headers
from onadata.libs.renderers.renderers import (
    MediaFileContentNegotiation,
    XFormListRenderer,
    XFormManifestRenderer,
)
from onadata.libs.serializers.xform_serializer import (
    XFormListSerializer,
    XFormManifestSerializer,
)
from onadata.libs.utils.cache_tools import (
    XFORM_MANIFEST_CACHE,
    XFROM_LIST_CACHE_TTL,
    safe_cache_get,
    safe_cache_set,
)
from onadata.libs.utils.common_tags import GROUP_DELIMETER_TAG, REPEAT_INDEX_TAGS
from onadata.libs.utils.export_builder import ExportBuilder

BaseViewset = get_baseviewset_class()


# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, "DEFAULT_CONTENT_LENGTH", 10000000)


# pylint: disable=too-many-ancestors
class XFormListViewSet(ETagsMixin, BaseViewset, viewsets.ReadOnlyModelViewSet):
    """
    OpenRosa Form List API - https://docs.getodk.org/openrosa-form-list/
    """

    authentication_classes = (
        DigestAuthentication,
        EnketoTokenAuthentication,
        TokenAuthentication,
    )
    content_negotiation_class = MediaFileContentNegotiation
    filterset_class = filters.FormIDFilter
    filter_backends = (
        filters.XFormListObjectPermissionFilter,
        filters.XFormListXFormPKFilter,
        django_filter_filters.DjangoFilterBackend,
    )
    queryset = XForm.objects.filter(
        downloadable=True, deleted_at=None, is_merged_dataset=False
    ).only(
        "id_string", "title", "version", "uuid", "description", "user__username", "hash"
    )
    permission_classes = (permissions.AllowAny,)
    renderer_classes = (XFormListRenderer,)
    serializer_class = XFormListSerializer
    template_name = "api/xformsList.xml"
    throttle_scope = "xformlist"

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {self.lookup_field: self.kwargs[self.lookup_field]}
        obj = get_object_or_404(queryset or XForm, **filter_kwargs)
        self.check_object_permissions(self.request, obj)

        if self.request.user.is_anonymous and obj.require_auth:
            self.permission_denied(self.request)

        return obj

    def get_serializer_class(self):
        """Return the class to use for the serializer"""
        if self.action == "manifest":
            return XFormManifestSerializer

        return super().get_serializer_class()

    def get_serializer(self, *args, **kwargs):
        """
        Return the serializer instance that should be used for validating and
        deserializing input, and for serializing output.
        """
        if self.action == "manifest":
            kwargs.setdefault("context", self.get_serializer_context())
            kwargs["context"][GROUP_DELIMETER_TAG] = ExportBuilder.GROUP_DELIMITER_DOT
            kwargs["context"][REPEAT_INDEX_TAGS] = "_,_"

        return super().get_serializer(*args, **kwargs)

    def filter_queryset(self, queryset):
        username = self.kwargs.get("username")
        form_pk = self.kwargs.get("xform_pk")
        project_pk = self.kwargs.get("project_pk")
        if (
            not username and not form_pk and not project_pk
        ) and self.request.user.is_anonymous:
            # raises a permission denied exception, forces authentication
            self.permission_denied(self.request)

        profile = None
        if username:
            profile = get_object_or_404(UserProfile, user__username__iexact=username)
        elif form_pk:
            queryset = queryset.filter(pk=form_pk)
            if queryset.first():
                profile = queryset.first().user.profile
        elif project_pk:
            queryset = queryset.filter(project__pk=project_pk)
            if queryset.first():
                profile = queryset.first().user.profile
        if profile:
            if profile.require_auth and self.request.user.is_anonymous:
                # raises a permission denied exception, forces authentication
                self.permission_denied(self.request)
            else:
                queryset = queryset.filter(user=profile.user, downloadable=True)

        queryset = super().filter_queryset(queryset)
        if not self.request.user.is_anonymous:
            xform_pk = self.kwargs.get("xform_pk")
            if (
                self.action == "list"
                and profile
                and xform_pk is None
                and project_pk is None
            ):
                forms_shared_with_user = get_forms_shared_with_user(profile.user)
                id_string = self.request.query_params.get("formID")
                forms_shared_with_user = (
                    forms_shared_with_user.filter(id_string=id_string)
                    if id_string
                    else forms_shared_with_user
                )
                queryset = queryset | forms_shared_with_user
                if self.request.user != profile.user:
                    public_forms = profile.user.xforms.filter(
                        downloadable=True, shared=True
                    )
                    queryset = queryset | public_forms

        return queryset

    def _get_xform_list_cache_key(self):
        xform_pk = self.kwargs.get("xform_pk")
        project_pk = self.kwargs.get("project_pk")
        cache_key = None

        if xform_pk:
            xform = get_object_or_404(XForm, pk=xform_pk)
            cache_key = get_xform_list_cache_key(self.request.user, xform)

        elif project_pk:
            project = get_object_or_404(Project, pk=project_pk)
            cache_key = get_xform_list_cache_key(self.request.user, project)

        return cache_key

    def list(self, request, *args, **kwargs):
        headers = get_openrosa_headers(request, location=False)

        if request.method in ["HEAD"]:
            return Response("", headers=headers, status=204)

        cache_key = self._get_xform_list_cache_key()

        if cache_key is not None:
            cached_result = safe_cache_get(cache_key)

            if cached_result is not None:
                return Response(cached_result, headers=headers)

        # pylint: disable=attribute-defined-outside-init
        self.object_list = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(self.object_list, many=True)

        if cache_key is not None:
            safe_cache_set(cache_key, serializer.data, XFROM_LIST_CACHE_TTL)

        return Response(serializer.data, headers=headers)

    def retrieve(self, request, *args, **kwargs):
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()

        return Response(
            self.object.xml, headers=get_openrosa_headers(request, location=False)
        )

    @action(
        methods=["GET", "HEAD"], detail=True, renderer_classes=[XFormManifestRenderer]
    )
    def manifest(self, request, *args, **kwargs):
        """A manifest defining additional supporting objects."""
        # pylint: disable=attribute-defined-outside-init
        xform = self.get_object()
        cache_key = f"{XFORM_MANIFEST_CACHE}{xform.pk}"
        cached_manifest: str | None = safe_cache_get(cache_key)
        # Ensure a previous stream has completed updating the cache by
        # confirm the last tag </manifest> exists
        if cached_manifest is not None and cached_manifest.endswith("</manifest>"):
            return Response(
                cached_manifest,
                content_type="text/xml; charset=utf-8",
                headers=get_openrosa_headers(request, location=False),
            )

        metadata_qs = MetaData.objects.filter(data_type="media", object_id=xform.pk)
        renderer = XFormManifestRenderer(cache_key)

        return StreamingHttpResponse(
            renderer.stream_data(metadata_qs, self.get_serializer),
            content_type="text/xml; charset=utf-8",
            headers=get_openrosa_headers(request, location=False),
        )

    @action(methods=["GET", "HEAD"], detail=True)
    def media(self, request, *args, **kwargs):
        """Returns the media file contents."""
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        media_pk = kwargs.get("metadata")

        if not media_pk:
            raise Http404()

        meta_obj = get_object_or_404(
            MetaData, data_type="media", object_id=self.object.pk, pk=media_pk
        )
        response = get_media_file_response(meta_obj, request)

        if response.status_code == 403 and request.user.is_anonymous:
            # raises a permission denied exception, forces authentication
            self.permission_denied(request)

        return response


class PreviewXFormListViewSet(XFormListViewSet):
    """
    OpenRosa Form List API - for preview purposes only
    """

    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    permission_classes = (permissions.AllowAny,)
