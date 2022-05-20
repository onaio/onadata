# -*- coding: utf-8 -*-
"""
Clone an XForm serializer.
"""
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from rest_framework import serializers

from onadata.libs.models.clone_xform import CloneXForm
from onadata.libs.serializers.fields.project_field import ProjectField
from onadata.libs.serializers.fields.xform_field import XFormField


class CloneXFormSerializer(serializers.Serializer):
    """Clone an xform serializer class"""

    xform = XFormField()
    username = serializers.CharField(max_length=255)
    project = ProjectField(required=False)

    # pylint: disable=no-self-use
    def create(self, validated_data):
        """Uses  the CloneXForm class to clone/copy an XForm.

        Returns the CloneXForm instance."""
        instance = CloneXForm(**validated_data)
        instance.save()

        return instance

    # pylint: disable=no-self-use
    def update(self, instance, validated_data):
        instance.xform = validated_data.get("xform", instance.xform)
        instance.username = validated_data.get("username", instance.username)
        instance.project = validated_data.get("project", instance.project)
        instance.save()

        return instance

    # pylint: disable=no-self-use
    def validate_username(self, value):
        """Check that the username exists"""
        # pylint: disable=invalid-name
        User = get_user_model()  # noqa N806
        try:
            User.objects.get(username=value)
        except User.DoesNotExist as e:
            raise serializers.ValidationError(
                _(f"User '{value}' does not exist.")
            ) from e

        return value
