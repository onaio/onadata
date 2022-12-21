# -*- coding: utf-8 -*-
"""
The /api/v1/orgs API implementation

List, Retrieve, Update, Create/Register Organizations.
"""
import json

from django.conf import settings
from django.core.cache import cache
from django.utils.module_loading import import_string

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from onadata.apps.api import permissions
from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.tools import get_baseviewset_class
from onadata.libs.filters import (
    OrganizationPermissionFilter,
    OrganizationsSharedWithUserFilter,
)
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.organization_member_serializer import (
    OrganizationMemberSerializer,
)
from onadata.libs.serializers.organization_serializer import OrganizationSerializer
from onadata.libs.utils.cache_tools import ORG_PROFILE_CACHE, safe_delete
from onadata.libs.utils.common_tools import merge_dicts

BaseViewset = get_baseviewset_class()


def serializer_from_settings():
    """Return the OrganizationSerializer either from settings or the default."""
    if settings.ORG_PROFILE_SERIALIZER:
        return import_string(settings.ORG_PROFILE_SERIALIZER)

    return OrganizationSerializer


# pylint: disable=too-many-ancestors
class OrganizationProfileViewSet(
    AuthenticateHeaderMixin,
    CacheControlMixin,
    ETagsMixin,
    ObjectLookupMixin,
    BaseViewset,
    ModelViewSet,
):
    """
    List, Retrieve, Update, Create/Register Organizations.
    """

    queryset = OrganizationProfile.objects.filter(user__is_active=True)
    serializer_class = serializer_from_settings()
    lookup_field = "user"
    permission_classes = [permissions.OrganizationProfilePermissions]
    filter_backends = (OrganizationPermissionFilter, OrganizationsSharedWithUserFilter)

    def retrieve(self, request, *args, **kwargs):
        """Get organization from cache or db"""
        username = kwargs.get("user")
        cached_org = cache.get(f"{ORG_PROFILE_CACHE}{username}")
        if cached_org:
            return Response(cached_org)
        response = super().retrieve(request, *args, **kwargs)
        cache.set(f"{ORG_PROFILE_CACHE}{username}", response.data)
        return response

    def create(self, request, *args, **kwargs):
        """Create and cache organization"""
        response = super().create(request, *args, **kwargs)
        organization = response.data
        username = organization.get("org")
        cache.set(f"{ORG_PROFILE_CACHE}{username}", organization)
        return response

    def destroy(self, request, *args, **kwargs):
        """Clear cache and destroy organization"""
        username = kwargs.get("user")
        safe_delete(f"{ORG_PROFILE_CACHE}{username}")
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update org in cache and db"""
        username = kwargs.get("user")
        response = super().update(request, *args, **kwargs)
        cache.set(f"{ORG_PROFILE_CACHE}{username}", response.data)
        return response

    @action(methods=["DELETE", "GET", "POST", "PUT"], detail=True)
    def members(self, request, *args, **kwargs):
        """Return organization members."""
        organization = self.get_object()
        data = merge_dicts(
            request.data, request.query_params.dict(), {"organization": organization.pk}
        )

        if request.method == "POST" and "username" not in data:
            data["username"] = None

        if request.method == "DELETE":
            data["remove"] = True

        if request.method == "PUT" and "role" not in data:
            data["role"] = None

        serializer = OrganizationMemberSerializer(data=data)

        username = kwargs.get("user")
        if serializer.is_valid():
            serializer.save()
            organization = serializer.validated_data.get("organization")
            data = OrganizationSerializer(
                organization, context={"request": request}
            ).data
            cache.set(f"{ORG_PROFILE_CACHE}{username}", data)
        else:
            return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # pylint: disable=attribute-defined-outside-init
        self.etag_data = json.dumps(data)
        resp_status = (
            status.HTTP_201_CREATED if request.method == "POST" else status.HTTP_200_OK
        )

        return Response(status=resp_status, data=serializer.data)
