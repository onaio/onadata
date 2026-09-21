"""
Organization serializer for v2 API
"""

from django.contrib.auth import get_user_model

from rest_framework import serializers

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.viewsets.organization_profile_viewset import (
    serializer_from_settings as serializer_from_settings_v1,
)
from onadata.libs.permissions import get_role_in_org
from onadata.libs.utils.gravatar import get_gravatar_img_link

# pylint: disable=invalid-name
User = get_user_model()
OrganizationSerializerV1 = serializer_from_settings_v1()


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

    An organization's users are left out: they are costly to build for every
    organization in a list. They are returned by the members endpoint.
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
            "creator",
            "name",
            "city",
            "country",
            "home_page",
            "twitter",
            "description",
            "require_auth",
            "address",
            "phonenumber",
            "num_of_submissions",
            "date_modified",
        )


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
