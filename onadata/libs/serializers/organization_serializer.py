# -*- coding: utf-8 -*-
"""
Organization Serializer
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models.query import QuerySet
from django.utils.translation import gettext as _

from rest_framework import serializers

from onadata.apps.api import tools
from onadata.apps.api.models import OrganizationProfile
from onadata.apps.api.tools import (
    _get_first_last_names,
    get_organization_members,
    get_organization_owners,
)
from onadata.apps.logger.models import KMSKey
from onadata.apps.main.forms import RegistrationFormUserProfile
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs.exceptions import EncryptionError
from onadata.libs.kms.tools import rotate_key
from onadata.libs.permissions import get_role_in_org
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.utils.model_tools import queryset_iterator

# pylint: disable=invalid-name
User = get_user_model()


class OrganizationSerializer(serializers.HyperlinkedModelSerializer):
    """
    Organization profile serializer
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="organizationprofile-detail", lookup_field="user"
    )
    org = serializers.CharField(source="user.username", max_length=30)
    user = serializers.HyperlinkedRelatedField(
        view_name="user-detail", lookup_field="username", read_only=True
    )
    email = serializers.EmailField(allow_blank=True)
    creator = serializers.HyperlinkedRelatedField(
        view_name="user-detail", lookup_field="username", read_only=True
    )
    users = serializers.SerializerMethodField()
    metadata = JsonField(required=False)
    name = serializers.CharField(max_length=30)
    active_kms_key = serializers.SerializerMethodField()
    inactive_kms_keys = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationProfile
        exclude = ("created_by", "is_organization", "organization")
        owner_only_fields = ("metadata", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and hasattr(self.Meta, "owner_only_fields"):
            request = self.context.get("request")
            is_permitted = (
                request
                and request.user
                and request.user.has_perm("api.view_organizationprofile", self.instance)
            )
            if isinstance(self.instance, QuerySet) or not is_permitted or not request:
                for field in getattr(self.Meta, "owner_only_fields"):
                    self.fields.pop(field)

    def update(self, instance, validated_data):
        """Update organization profile properties."""
        # update the user model
        if "name" in validated_data:
            first_name, last_name = _get_first_last_names(validated_data.get("name"))
            instance.user.first_name = first_name
            instance.user.last_name = last_name

        if "email" in validated_data:
            instance.email = validated_data.pop("email")

        instance.user.save()
        return super().update(instance, validated_data)

    def create(self, validated_data):
        """Create an organization profile."""
        org = validated_data.get("user")
        if org:
            org = org.get("username")

        org_name = validated_data.get("name", None)
        creator = None

        if "request" in self.context:
            creator = self.context["request"].user
            validated_data["host"] = self.context["request"].get_host()

        validated_data["organization"] = org_name

        profile = tools.create_organization_object(org, creator, validated_data)
        profile.save()

        return profile

    def validate_org(self, value):
        """
        Validate organization name.
        """
        org = value.lower() if isinstance(value, str) else value

        if org in RegistrationFormUserProfile.RESERVED_USERNAMES:
            raise serializers.ValidationError(
                _(f"{org} is a reserved name, please choose another")
            )
        if not RegistrationFormUserProfile.legal_usernames_re.search(org):
            raise serializers.ValidationError(
                _(
                    "Organization may only contain alpha-numeric characters and "
                    "underscores"
                )
            )
        try:
            User.objects.get(username=org)
        except User.DoesNotExist:
            return org

        raise serializers.ValidationError(_(f"Organization {org} already exists."))

    def get_users(self, obj):
        """
        Return organization members.
        """

        def _create_user_list(user_list):
            users_list = []
            for u in user_list:
                try:
                    profile = u.profile
                except UserProfile.DoesNotExist:
                    profile = UserProfile.objects.create(user=u)

                users_list.append(
                    {
                        "user": u.username,
                        "role": get_role_in_org(u, obj),
                        "first_name": u.first_name,
                        "last_name": u.last_name,
                        "gravatar": profile.gravatar,
                    }
                )
            return users_list

        members = get_organization_members(obj) if obj else []
        owners = get_organization_owners(obj) if obj else []

        if owners and members:
            members = members.exclude(username__in=[user.username for user in owners])

        members_list = _create_user_list(members)
        owners_list = _create_user_list(owners)

        return owners_list + members_list

    def _get_kms_key_data(self, key):
        """Get the KMSKey data."""
        return {
            "description": key.description,
            "date_created": key.date_created.isoformat(),
            "is_expired": key.is_expired,
            "expiry_date": key.expiry_date.isoformat() if key.expiry_date else None,
            "grace_end_date": (
                key.grace_end_date.isoformat() if key.grace_end_date else None
            ),
        }

    def get_inactive_kms_keys(self, obj):
        """Get the inactive KMSKeys for organization."""
        content_type = ContentType.objects.get_for_model(OrganizationProfile)
        # All keys except the latest one
        kms_key_qs = KMSKey.objects.filter(
            content_type=content_type, object_id=obj.pk, disabled_at__isnull=True
        ).order_by("-date_created")[1:]
        inactive_keys = []

        for key in queryset_iterator(kms_key_qs):
            inactive_keys.append(self._get_kms_key_data(key))

        return inactive_keys

    def get_active_kms_key(self, obj):
        """Get the active KMSKey for organization."""
        content_type = ContentType.objects.get_for_model(OrganizationProfile)

        try:
            # Get the latest key created
            kms_key = KMSKey.objects.filter(
                content_type=content_type, object_id=obj.pk, disabled_at__isnull=True
            ).latest("date_created")
        except KMSKey.DoesNotExist:
            return None

        return self._get_kms_key_data(kms_key)


class RotateOrganizationKeySerializer(serializers.Serializer):
    """Serializer for manual key rotation."""

    user = serializers.HyperlinkedRelatedField(
        view_name="user-detail", lookup_field="username", read_only=True
    )
    key_id = serializers.CharField()

    def validate_key_id(self, value):
        content_type = ContentType.objects.get_for_model(OrganizationProfile)
        organization = self.context["organization"]

        try:
            self.kms_key = KMSKey.objects.get(
                key_id=value, content_type=content_type, object_id=organization.pk
            )

        except KMSKey.DoesNotExist:
            raise serializers.ValidationError(
                "Key does not exist.", code="does_not_exist"
            )

        if self.kms_key.disabled_at:
            raise serializers.ValidationError("Key is inactive.")

        if self.kms_key.rotated_at:
            raise serializers.ValidationError("Key already rotated.")

        return value

    def save(self, **kwargs):
        try:
            rotate_key(
                self.kms_key,
                rotated_by=self.context["request"].user,
                manual=True,
            )
        except EncryptionError as exc:
            raise serializers.ValidationError({"key_id": f"{exc}"})
