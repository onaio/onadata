# -*- coding: utf-8 -*-
"""
The /api/v1/orgs API implementation

List, Retrieve, Update, Create/Register Organizations.
"""

import json

from django.conf import settings
from django.utils.module_loading import import_string

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from onadata.apps.api import permissions
from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.tools import get_baseviewset_class, get_org_profile_cache_key
from onadata.apps.logger.models import KMSKey
from onadata.apps.messaging.constants import KMS_KEY, KMS_KEY_ROTATED
from onadata.apps.messaging.serializers import send_message
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
from onadata.libs.serializers.organization_serializer import (
    KMSKeyInlineSerializer,
    OrganizationSerializer,
    RotateOrganizationKeySerializer,
)
from onadata.libs.utils.cache_tools import (
    safe_cache_delete,
    safe_cache_get,
    safe_cache_set,
)
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

    def get_serializer_class(self):
        """Override `get_serializer_class` method"""
        if self.action == "rotate_key":
            return RotateOrganizationKeySerializer

        return super().get_serializer_class()

    def retrieve(self, request, *args, **kwargs):
        """Get organization from cache or db"""
        organization = self.get_object()
        cache_key = get_org_profile_cache_key(request.user, organization)
        cached_org = safe_cache_get(cache_key)

        if cached_org:
            return Response(cached_org)

        response = super().retrieve(request, *args, **kwargs)
        safe_cache_set(cache_key, response.data)
        return response

    def create(self, request, *args, **kwargs):
        """Create and cache organization"""
        response = super().create(request, *args, **kwargs)
        organization = response.data
        username = organization.get("org")
        organization_profile = OrganizationProfile.objects.get(user__username=username)
        cache_key = get_org_profile_cache_key(request.user, organization_profile)
        safe_cache_set(cache_key, organization)
        return response

    def destroy(self, request, *args, **kwargs):
        """Clear cache and destroy organization"""
        cache_key = get_org_profile_cache_key(request.user, self.get_object())
        safe_cache_delete(cache_key)
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update org in cache and db"""
        response = super().update(request, *args, **kwargs)
        cache_key = get_org_profile_cache_key(request.user, self.get_object())
        safe_cache_set(cache_key, response.data)
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

        if not serializer.is_valid():
            return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        data = self.serializer_class(organization, context={"request": request}).data
        # pylint: disable=attribute-defined-outside-init
        self.etag_data = json.dumps(data)
        resp_status = (
            status.HTTP_201_CREATED if request.method == "POST" else status.HTTP_200_OK
        )

        return Response(status=resp_status, data=serializer.data)

    @action(methods=["POST"], detail=True, url_path="rotate-key")
    def rotate_key(self, request, *args, **kwargs):
        """Manually rotate KMS key."""
        self.get_object()  # Check if user has permission to rotate key
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_key = KMSKey.objects.get(id=serializer.validated_data["id"])
        new_key = serializer.save()
        # Capture audit log
        send_message(
            instance_id=old_key.id,
            target_id=old_key.id,
            target_type=KMS_KEY,
            user=request.user,
            message_verb=KMS_KEY_ROTATED,
        )
        data = KMSKeyInlineSerializer(new_key).data
        return Response(data, status=status.HTTP_200_OK)
