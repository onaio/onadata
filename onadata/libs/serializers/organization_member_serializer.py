from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from rest_framework import serializers

from onadata.libs.serializers.fields.organization_field import \
    OrganizationField
from onadata.libs.permissions import ROLES
from onadata.libs.permissions import is_organization
from onadata.apps.api.tools import add_user_to_organization


class OrganizationMemberSerializer(serializers.Serializer):
    organization = OrganizationField()
    username = serializers.CharField(max_length=255)
    role = serializers.CharField(max_length=50, required=False)

    def validate_username(self, value):
        """Check that the username exists"""

        user = None
        try:
            user = User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(_(
                u"User '%(value)s' does not exist." % {"value": value}
            ))
        else:
            if not user.is_active:
                raise serializers.ValidationError(_(u"User is not active"))

            if is_organization(user.profile):
                raise serializers.ValidationError(
                    _(u"Cannot add org account `{}` as member."
                      .format(user.username)))

        return value

    def validate_role(self, value):
        """check that the role exists"""
        if value not in ROLES:
            raise serializers.ValidationError(_(
                u"Unknown role '%(role)s'." % {"role": value}
            ))

        return value

    def create(self, validated_data):
        organization = validated_data.get("organization")
        username = validated_data.get("username")
        user = User.objects.get(username=username)
        role = validated_data.get('role')

        add_user_to_organization(organization, user)

    def update(self, instance, validated_data):
        organization = validated_data.get('organization')
        username = validated_data.get('username')
        role = validated_data.get('role')
        user = User.objects.get(username=username)

        add_user_to_organization(organization, user)
