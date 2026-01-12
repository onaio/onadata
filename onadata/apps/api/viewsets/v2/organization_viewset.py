# -*- coding: utf-8 -*-
"""
Organization viewset for v2 API
"""

from rest_framework.response import Response

from onadata.apps.api.tools import get_org_profile_cache_key
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet as OrganizationProfileViewSetV1,
)
from onadata.libs.serializers.v2.organization_serializer import (
    OrganizationListSerializer,
    OrganizationPrivateSerializer,
    OrganizationSerializer,
)
from onadata.libs.utils.cache_tools import safe_cache_get, safe_cache_set


# pylint: disable=too-many-ancestors
class OrganizationProfileViewSet(OrganizationProfileViewSetV1):
    """
    List, Retrieve, Update, Create/Register Organizations (v2 API).

    The v2 API excludes the 'users' field from list responses to improve
    performance by reducing database queries. The full details including
    users are still available in the detail endpoint.
    """

    serializer_class = OrganizationSerializer

    def get_serializer_class(self):
        """Get serializer class based on action

        Overrides super().get_serializer_class()
        """
        if self.action == "list":
            return OrganizationListSerializer

        return super().get_serializer_class()

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single Organization

        Overrides super().retrieve() to separate cached base data from
        user-specific private data.
        """
        organization = self.get_object()
        cache_key = get_org_profile_cache_key(request.user, organization)
        base_cache_key = f"{cache_key}_base"

        # Try to get base data from cache
        base_data = safe_cache_get(base_cache_key)

        if base_data is None:
            # Generate base data (cacheable across users)
            base_data = OrganizationSerializer(
                organization, context={"request": request}
            ).data

            # Cache base data
            safe_cache_set(base_cache_key, base_data)

        # Inject user specific fields (not cached)
        private_data = OrganizationPrivateSerializer(
            organization, context={"request": request}
        ).data

        # Cache complete response for this user
        response_data = {**base_data, **private_data}
        safe_cache_set(cache_key, response_data)

        return Response(response_data)
