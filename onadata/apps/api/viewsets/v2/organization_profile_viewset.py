"""
OrganizationProfile viewset for v2 API
"""

import json

from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from onadata.apps.api.tools import (
    get_organization_members,
    get_organization_owners,
)
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet as OrganizationProfileViewSetV1,
)
from onadata.apps.api.viewsets.organization_profile_viewset import (
    serializer_from_settings as serializer_from_settings_v1,
)
from onadata.libs.filters import (
    OrganizationPermissionFilter,
    OrganizationRoleFilter,
    OrganizationsSharedWithUserFilter,
)
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.serializers.v2.organization_serializer import (
    OrganizationListSerializer,
    OrganizationMemberListSerializer,
)


def serializer_from_settings():
    """Return the v1 serializer, from settings or the default, linking to v2."""

    class OrganizationSerializer(serializer_from_settings_v1()):
        """Organization profile serializer for v2 API"""

        url = serializers.HyperlinkedIdentityField(
            view_name="organizationprofile-v2-detail", lookup_field="user"
        )

    return OrganizationSerializer


# pylint: disable=too-many-ancestors
class OrganizationProfileViewSet(OrganizationProfileViewSetV1):
    """List, Retrieve, Update, Create/Register Organizations."""

    # Ordered so that pages neither overlap nor skip records
    queryset = OrganizationProfileViewSetV1.queryset.order_by("user__username")
    serializer_class = serializer_from_settings()
    filter_backends = (
        OrganizationPermissionFilter,
        OrganizationsSharedWithUserFilter,
        OrganizationRoleFilter,
        SearchFilter,
    )
    search_fields = ("name", "user__username")
    pagination_class = StandardPageNumberPagination
    api_version = "v2"

    def get_serializer_class(self):
        """Get serializer class based on action

        Overrides super().get_serializer_class()
        """
        if self.action == "list":
            return OrganizationListSerializer

        return super().get_serializer_class()

    @action(methods=["DELETE", "GET", "POST", "PUT"], detail=True)
    def members(self, request, *args, **kwargs):
        """Return organization members, or add, update or remove a member.

        Overrides super().members()
        """
        if request.method != "GET":
            return super().members(request, *args, **kwargs)

        organization = self.get_object()
        # Owners first, as in an organization's `users`
        owners = list(get_organization_owners(organization))
        members = get_organization_members(organization).exclude(
            pk__in=[owner.pk for owner in owners]
        )
        serializer = OrganizationMemberListSerializer(
            [*owners, *members],
            many=True,
            context={**self.get_serializer_context(), "organization": organization},
        )
        # pylint: disable=attribute-defined-outside-init
        self.etag_data = json.dumps(serializer.data)

        return Response(serializer.data)
