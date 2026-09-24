"""
OrganizationProfile viewset for v2 API
"""

from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.filters import SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.tools import (
    get_org_profile_cache_key,
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
    OrganizationMemberSerializer,
    OrganizationPrivateSerializer,
    OrganizationSerializer,
)
from onadata.libs.utils.cache_tools import safe_cache_get, safe_cache_set

# pylint: disable=invalid-name
User = get_user_model()


# pylint: disable=too-many-ancestors
class OrganizationProfileViewSet(OrganizationProfileViewSetV1):
    """List, Retrieve, Update, Create Organizations."""

    queryset = OrganizationProfileViewSetV1.queryset.select_related("user").order_by(
        "user__username"
    )
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

        if self.action == "members":
            if self.request.method == "GET":
                return OrganizationMemberListSerializer

            return OrganizationMemberSerializer

        return super().get_serializer_class()

    def get_object(self, queryset=None):
        """Get the organization by its username

        Overrides super().get_object(), which reads how to look up the
        organization from the `user` field of the serializer of the action.
        The serializers of the members have no such field.
        """
        if self.kwargs.get(self.lookup_field) is None:
            raise ParseError(f"Expected URL keyword argument `{self.lookup_field}`.")

        if queryset is None:
            queryset = self.filter_queryset(self.get_queryset())

        obj = get_object_or_404(queryset, user__username=self.kwargs[self.lookup_field])
        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single Organization

        Overrides super().retrieve()
        """
        organization = self.get_object()
        cache_key = get_org_profile_cache_key(
            request.user, organization, self.api_version
        )
        base_data = safe_cache_get(cache_key)

        if base_data is None:
            base_data = self.get_serializer(organization).data
            safe_cache_set(cache_key, base_data)

        return Response({**base_data, **self._get_private_data(organization)})

    def create(self, request, *args, **kwargs):
        """Create an Organization

        Overrides super().create(), which caches the response
        """
        response = super().create(request, *args, **kwargs)
        organization = OrganizationProfile.objects.get(
            user__username=response.data["org"]
        )
        response.data = {**response.data, **self._get_private_data(organization)}

        return response

    def update(self, request, *args, **kwargs):
        """Update an Organization

        Overrides super().update(), which caches the response
        """
        response = super().update(request, *args, **kwargs)
        # super() has checked that the user may update the organization
        organization = OrganizationProfile.objects.get(
            user__username=self.kwargs[self.lookup_field]
        )
        response.data = {**response.data, **self._get_private_data(organization)}

        return response

    def _get_private_data(self, organization):
        """Return the user specific fields, which are never cached"""
        return OrganizationPrivateSerializer(
            organization, context={"request": self.request}
        ).data

    @action(methods=["GET", "POST", "PUT", "PATCH"], detail=True)
    def members(self, request, *args, **kwargs):
        """Return organization members, or add, update or remove a member.

        A member is removed by updating with `remove`.

        Overrides super().members()
        """
        organization = self.get_object()
        context = {**self.get_serializer_context(), "organization": organization}

        if request.method != "GET":
            serializer = self.get_serializer(data=request.data, context=context)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            if serializer.validated_data["remove"]:
                return Response(status=status.HTTP_204_NO_CONTENT)

            member = User.objects.get(username=serializer.validated_data["username"])
            serializer = OrganizationMemberListSerializer(member, context=context)
            status_code = (
                status.HTTP_201_CREATED
                if request.method == "POST"
                else status.HTTP_200_OK
            )

            return Response(serializer.data, status=status_code)

        # The creator of an organization is an owner without being in the
        # members team, as an organization's `users` has it
        members = (
            get_organization_owners(organization)
            .union(get_organization_members(organization))
            .order_by("username")
        )
        serializer = self.get_serializer(members, many=True, context=context)
        return Response(serializer.data)
