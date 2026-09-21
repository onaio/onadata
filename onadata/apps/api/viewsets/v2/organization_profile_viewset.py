"""
OrganizationProfile viewset for v2 API
"""

import json

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
from onadata.libs.filters import (
    OrganizationPermissionFilter,
    OrganizationRoleFilter,
    OrganizationsSharedWithUserFilter,
)
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.serializers.v2.organization_serializer import (
    OrganizationListSerializer,
    OrganizationMemberListSerializer,
    OrganizationSerializer,
)


# pylint: disable=too-many-ancestors
class OrganizationProfileViewSet(OrganizationProfileViewSetV1):
    """List, Retrieve, Update, Create/Register Organizations."""

    # Ordered so that pages neither overlap nor skip records
    queryset = OrganizationProfileViewSetV1.queryset.order_by("user__username")
    serializer_class = OrganizationSerializer
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
        # The creator of an organization is an owner without being in the
        # members team, as an organization's `users` has it
        members = (
            get_organization_owners(organization)
            .union(get_organization_members(organization))
            .order_by("username")
        )
        serializer = OrganizationMemberListSerializer(
            members,
            many=True,
            context={**self.get_serializer_context(), "organization": organization},
        )
        # pylint: disable=attribute-defined-outside-init
        self.etag_data = json.dumps(serializer.data)

        return Response(serializer.data)
