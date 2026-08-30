# -*- coding: utf-8 -*-
"""
Organization serializer for v2 API
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from rest_framework import serializers

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.logger.models import KMSKey
from onadata.libs.permissions import CAN_ADD_ORGANIZATION_PROJECT, get_role_in_org
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.serializers.organization_serializer import KMSKeyInlineSerializer
from onadata.libs.serializers.organization_serializer import (
    OrganizationSerializer as OrganizationSerializerV1,
)

# pylint: disable=invalid-name
User = get_user_model()


def get_current_user_role(organization, request):
    """Return the role of the request user in the organization."""
    if request.user.is_anonymous:
        return None

    return get_role_in_org(request.user, organization)


class OrganizationListSerializer(serializers.HyperlinkedModelSerializer):
    """Serializer for a list of Organizations - excludes users field for performance"""

    url = serializers.HyperlinkedIdentityField(
        view_name="organizationprofile-v2-detail", lookup_field="user"
    )
    org = serializers.CharField(source="user.username", max_length=30)
    user = serializers.HyperlinkedRelatedField(
        view_name="user-detail", lookup_field="username", read_only=True
    )
    email = serializers.EmailField(allow_blank=True)
    creator = serializers.HyperlinkedRelatedField(
        view_name="user-detail", lookup_field="username", read_only=True
    )
    metadata = JsonField(required=False)
    name = serializers.CharField(max_length=30)
    encryption_keys = serializers.SerializerMethodField()
    current_user_role = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationProfile
        fields = [
            "url",
            "org",
            "user",
            "email",
            "creator",
            "metadata",
            "name",
            "encryption_keys",
            "current_user_role",
            "city",
            "country",
            "organization",
            "home_page",
            "twitter",
            "require_auth",
        ]
        owner_only_fields = ("metadata", "email", "encryption_keys")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and hasattr(self.Meta, "owner_only_fields"):
            request = self.context.get("request")
            is_owner = (
                request
                and request.user
                and hasattr(self.instance, "user")
                and request.user.has_perm(CAN_ADD_ORGANIZATION_PROJECT, self.instance)
            )
            if not is_owner or not request:
                for field in getattr(self.Meta, "owner_only_fields"):
                    if field in self.fields:
                        self.fields.pop(field)

    def get_current_user_role(self, obj):
        """
        Return the role of the request user in the organization.
        """
        return get_current_user_role(obj, self.context["request"])

    def get_encryption_keys(self, obj):
        """
        Get the encryption keys for organization.
        Imported from v1 serializer.
        """
        content_type = ContentType.objects.get_for_model(OrganizationProfile)
        kms_key_qs = KMSKey.objects.filter(
            content_type=content_type, object_id=obj.pk, disabled_at__isnull=True
        ).order_by("-date_created")

        return KMSKeyInlineSerializer(kms_key_qs, many=True).data


class OrganizationPrivateSerializer(serializers.ModelSerializer):
    """User specific fields for an Organization"""

    current_user_role = serializers.SerializerMethodField()

    def get_current_user_role(self, obj):
        """Return the role of the request user in the organization."""
        return get_current_user_role(obj, self.context["request"])

    class Meta:
        model = OrganizationProfile
        fields = ("current_user_role",)


class OrganizationSerializer(OrganizationSerializerV1):
    """Serializer for an Organization - includes all fields for detail view"""

    url = serializers.HyperlinkedIdentityField(
        view_name="organizationprofile-v2-detail", lookup_field="user"
    )
