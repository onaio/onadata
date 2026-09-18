"""
Organization serializer for v2 API
"""

from rest_framework import serializers

from onadata.apps.api.models.organization_profile import OrganizationProfile


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
