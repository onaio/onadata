# -*- coding: utf-8 -*-
"""
The /api/v1/orgs API implementation

List, Retrieve, Update, Create/Register Organizations.
"""

import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.module_loading import import_string

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.fields import empty
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from reversion.views import RevisionMixin

from onadata.apps.api import permissions
from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.tools import (
    get_baseviewset_class,
    get_org_profile_cache_key,
    invalidate_organization_cache,
)
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
from onadata.libs.permissions import ManagerRole, OwnerRole
from onadata.libs.serializers.organization_member_serializer import (
    OrganizationMemberListSerializer,
    OrganizationMemberSerializer,
)
from onadata.libs.serializers.organization_serializer import (
    KMSKeyInlineSerializer,
    OrganizationSerializer,
    RotateOrganizationKeySerializer,
)
from onadata.libs.stepup import RequiresStepUp
from onadata.libs.stepup.drf import incoming_value
from onadata.libs.stepup.policy import (
    GATE_GRANT_ORG_ADMIN,
    GATE_REQUIRE_AUTH,
    GATE_ROTATE_ORG_KEY,
)
from onadata.libs.utils.cache_tools import (
    safe_cache_delete,
    safe_cache_get,
    safe_cache_set,
)
from onadata.libs.utils.common_tools import merge_dicts

BaseViewset = get_baseviewset_class()
User = get_user_model()

ADMIN_ROLES = {role.name: role for role in (OwnerRole, ManagerRole)}


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
    RevisionMixin,
    RequiresStepUp,
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
    api_version = "v1"

    def get_serializer_class(self):
        """Override `get_serializer_class` method"""
        if self.action == "rotate_key":
            return RotateOrganizationKeySerializer

        return super().get_serializer_class()

    def retrieve(self, request, *args, **kwargs):
        """Get organization from cache or db"""
        organization = self.get_object()
        cache_key = get_org_profile_cache_key(
            request.user, organization, self.api_version
        )
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
        cache_key = get_org_profile_cache_key(
            request.user, organization_profile, self.api_version
        )
        safe_cache_set(cache_key, organization)
        return response

    def destroy(self, request, *args, **kwargs):
        """Clear cache and destroy organization"""
        cache_key = get_org_profile_cache_key(
            request.user, self.get_object(), self.api_version
        )
        safe_cache_delete(cache_key)
        return super().destroy(request, *args, **kwargs)

    def _require_auth_refusal(self, request, partial):
        """An organisation's profile is a UserProfile, so toggling its
        require_auth needs the same proof as on a personal profile."""
        organization = self.get_object()
        incoming = incoming_value(
            self.get_serializer(organization, partial=partial),
            "require_auth",
            request.data,
        )
        if incoming is empty or incoming == organization.require_auth:
            return None
        return self.check_step_up(request, GATE_REQUIRE_AUTH)

    def member_role_refusal(self, request, organization, validated_data):
        """Making someone an owner or manager lets them change every gated
        setting of the organisation with their own factor, so it needs the
        caller's. Checked after validation, so a rejected request does not
        spend the grant."""
        role = ADMIN_ROLES.get(validated_data.get("role"))
        username = validated_data.get("username")
        if validated_data.get("remove") or role is None or not username:
            return None
        if role.user_has_role(User.objects.get(username=username), organization):
            return None
        return self.check_step_up(request, GATE_GRANT_ORG_ADMIN)

    def update(self, request, *args, **kwargs):
        """Update org in cache and db"""
        refusal = self._require_auth_refusal(request, kwargs.get("partial", False))
        if refusal is not None:
            return refusal
        response = super().update(request, *args, **kwargs)
        organization = self.get_object()
        invalidate_organization_cache(organization.user.username)
        cache_key = get_org_profile_cache_key(
            request.user, organization, self.api_version
        )
        safe_cache_set(cache_key, response.data)
        return response

    @action(methods=["DELETE", "GET", "POST", "PUT"], detail=True)
    def members(self, request, *args, **kwargs):
        """Return organization members."""
        organization = self.get_object()

        if request.method == "GET":
            data = self.serializer_class(
                organization, context={"request": request}
            ).data
            # pylint: disable=attribute-defined-outside-init
            self.etag_data = json.dumps(data)

            return Response(OrganizationMemberListSerializer(organization).data)

        # Writes take their input from the request body; DELETE also accepts
        # the query string because clients cannot reliably send a DELETE body.
        # The body takes precedence so the username the permission check
        # authorized is the one acted on.
        query_params = (
            request.query_params.dict() if request.method == "DELETE" else {}
        )
        data = merge_dicts(
            query_params, request.data, {"organization": organization.pk}
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

        refusal = self.member_role_refusal(
            request, organization, serializer.validated_data
        )
        if refusal is not None:
            return refusal
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
        # Checks if user has permission to rotate key
        organization = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "organization": organization},
        )
        serializer.is_valid(raise_exception=True)
        refusal = self.check_step_up(request, GATE_ROTATE_ORG_KEY)
        if refusal is not None:
            return refusal
        old_key = serializer.validated_data["id"]
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
