"""
Organization serializer for v2 API
"""

from collections.abc import Mapping

from django.contrib.auth import get_user_model

from rest_framework import serializers

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.viewsets.organization_profile_viewset import (
    serializer_from_settings as serializer_from_settings_v1,
)
from onadata.libs.permissions import MemberRole, get_role_in_org
from onadata.libs.serializers.organization_member_serializer import (
    OrganizationMemberSerializer as OrganizationMemberSerializerV1,
)
from onadata.libs.utils.gravatar import get_gravatar_img_link

# pylint: disable=invalid-name
User = get_user_model()
OrganizationSerializerV1 = serializer_from_settings_v1()


def get_current_user_role(organization, request):
    """Return the role of the request user in the organization."""
    user = request.user

    if user.is_anonymous:
        return None

    role = get_role_in_org(user, organization)

    if role != MemberRole.name:
        return role

    # `member` is also what a user with no permissions on the organization
    # gets, so check that the user belongs to one of its teams
    if user.groups.filter(team__organization=organization.user).exists():
        return role

    return None


class OrganizationSerializer(OrganizationSerializerV1):
    """Serializer for an Organization

    Extends the v1 serializer, from settings or the default.
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="organizationprofile-v2-detail", lookup_field="user"
    )
    # Left out: an organization's users are returned by the members endpoint
    users = None


class OrganizationListSerializer(serializers.HyperlinkedModelSerializer):
    """Serializer for a list of Organizations

    Only what identifies an organization in a list. Its profile is returned
    when it is retrieved, and its users by the members endpoint.
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="organizationprofile-v2-detail", lookup_field="user"
    )
    org = serializers.CharField(source="user.username", read_only=True)
    user = serializers.HyperlinkedRelatedField(
        view_name="user-detail", lookup_field="username", read_only=True
    )
    creator = serializers.HyperlinkedRelatedField(
        view_name="user-detail", lookup_field="username", read_only=True
    )

    class Meta:
        model = OrganizationProfile
        fields = (
            "url",
            "org",
            "user",
            "name",
            "creator",
            "num_of_submissions",
            "date_modified",
        )


class OrganizationPrivateSerializer(serializers.ModelSerializer):
    """User specific fields for an Organization"""

    current_user_role = serializers.SerializerMethodField()

    def get_current_user_role(self, obj):
        """Return the role of the request user in the organization."""
        return get_current_user_role(obj, self.context["request"])

    class Meta:
        model = OrganizationProfile
        fields = ("current_user_role",)


class OrganizationMemberListSerializer(serializers.ModelSerializer):
    """Serializer for a list of an Organization's members

    A member is returned as in an organization's `users`. The organization is
    passed in the context.
    """

    user = serializers.CharField(source="username", read_only=True)
    role = serializers.SerializerMethodField()
    gravatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("user", "role", "first_name", "last_name", "gravatar")

    def get_role(self, obj):
        """Return the role of the member in the organization."""
        return get_role_in_org(obj, self.context["organization"])

    def get_gravatar(self, obj):
        """Return the Gravatar URL of the member."""
        return get_gravatar_img_link(obj)


class OrganizationMemberSerializer(OrganizationMemberSerializerV1):
    """Serializer for adding, updating and removing a member of an Organization

    A member is added on POST. On PUT and PATCH the role of the member is
    changed, or the member is removed if `remove` is true. The organization
    and the request are passed in the context.
    """

    username = serializers.CharField(max_length=255)
    # Not part of the input: the organization is the one being accessed
    organization = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # The role is what changes when a member is updated, unless the
        # member is being removed
        self.fields["role"].required = self._is_update() and not self._is_remove()

    def _is_update(self):
        request = self.context.get("request")

        return request is not None and request.method in ("PUT", "PATCH")

    def _is_remove(self):
        # There is no input when the serializer is not given data, and the
        # input may not be an object
        initial_data = getattr(self, "initial_data", None)
        remove = (
            initial_data.get("remove") if isinstance(initial_data, Mapping) else None
        )

        return self._is_update() and remove in serializers.BooleanField.TRUE_VALUES

    def validate(self, attrs):
        attrs["organization"] = self.context["organization"]
        # A member is only removed when updating
        attrs["remove"] = self._is_remove()

        return super().validate(attrs)
