"""
OrganizationProfile viewset for v2 API
"""

from rest_framework import serializers
from rest_framework.filters import SearchFilter

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
