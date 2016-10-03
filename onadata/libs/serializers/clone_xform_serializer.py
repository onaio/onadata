from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from rest_framework import serializers
from onadata.libs.models.clone_xform import CloneXForm
from onadata.libs.serializers.fields.xform_field import XFormField
from onadata.libs.serializers.fields.project_field import ProjectField


class CloneXFormSerializer(serializers.Serializer):
    xform = XFormField()
    username = serializers.CharField(max_length=255)
    project = ProjectField(required=False)

    def create(self, validated_data):
        instance = CloneXForm(**validated_data)
        instance.save()

        return instance

    def update(self, instance, validated_data):
        instance.xform = validated_data.get('xform', instance.xform)
        instance.username = validated_data.get('username', instance.username)
        instance.project = validated_data.get('project', instance.project)
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
