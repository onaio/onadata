"""
OrganizationProfile viewset for v2 API
"""

import json

from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

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


def serializer_from_settings():
    """Return the v1 serializer, from settings or the default, linking to v2."""

    class OrganizationSerializer(serializer_from_settings_v1()):
        """Organization profile serializer for v2 API"""

        url = serializers.HyperlinkedIdentityField(
            view_name="organizationprofile-v2-detail", lookup_field="user"
        )

    return OrganizationSerializer


def list_serializer_from(serializer_class):
    """Return the serializer without an organization's users.

    They are costly to build for every organization in a list. They are
    returned by the members endpoint instead.
    """

    # pylint: disable=too-few-public-methods
    class OrganizationListSerializer(serializer_class):
        """Organization profile list serializer for v2 API"""

        def get_fields(self):
            """Leave out `users`

            Overrides super().get_fields()
            """
            fields = super().get_fields()
            fields.pop("users", None)

            return fields

    return OrganizationListSerializer


# pylint: disable=too-many-ancestors
class OrganizationProfileViewSet(OrganizationProfileViewSetV1):
    """List, Retrieve, Update, Create/Register Organizations."""

    # Ordered so that pages neither overlap nor skip records
    queryset = OrganizationProfileViewSetV1.queryset.order_by("user__username")
    serializer_class = serializer_from_settings()
    list_serializer_class = list_serializer_from(serializer_class)
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
            return self.list_serializer_class

        return super().get_serializer_class()

    @action(methods=["DELETE", "GET", "POST", "PUT"], detail=True)
    def members(self, request, *args, **kwargs):
        """Return organization members, or add, update or remove a member.

        Overrides super().members()
        """
        if request.method != "GET":
            return super().members(request, *args, **kwargs)

        organization = self.get_object()
        # Members are returned as they are in an organization's `users`
        users_field = self.get_serializer(organization).fields["users"]
        users = users_field.to_representation(users_field.get_attribute(organization))
        # pylint: disable=attribute-defined-outside-init
        self.etag_data = json.dumps(users)

        return Response(users)
