from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from rest_framework import serializers
from onadata.libs.models.share_xform import ShareXForm
from onadata.libs.permissions import ROLES
from onadata.libs.serializers.fields.xform_field import XFormField


class ShareXFormSerializer(serializers.Serializer):
    xform = XFormField()
    username = serializers.CharField(max_length=255)
    role = serializers.CharField(max_length=50)

    def update(self, instance, validated_data):
        instance.xform = validated_data.get('xform', instance.xform)
        instance.username = validated_data.get('username', instance.username)
        instance.role = validated_data.get('role', instance.role)
        instance.save()

        return instance

    def create(self, validated_data):
        instance = ShareXForm(**validated_data)
        instance.save()

        return instance

    def validate_username(self, value):
        """Check that the username exists"""
        try:
            User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(_(
                u"User '%(value)s' does not exist." % {"value": value}
            ))

        return value

    def validate_role(self, value):
        """check that the role exists"""
        if value not in ROLES:
            raise serializers.ValidationError(_(
                u"Unknown role '%(role)s'." % {"role": value}
            ))

        return value
