# -*- coding: utf-8 -*-
"""
Share XForm serializer.
"""
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from rest_framework import serializers

from onadata.libs.models.share_xform import ShareXForm
from onadata.libs.permissions import ROLES
from onadata.libs.serializers.fields.xform_field import XFormField


class ShareXFormSerializer(serializers.Serializer):
    """Share xform to a user."""

    xform = XFormField()
    username = serializers.CharField(max_length=255)
    role = serializers.CharField(max_length=50)

    # pylint: disable=unused-argument,no-self-use
    def update(self, instance, validated_data):
        """Make changes to form share to a user."""
        instance.xform = validated_data.get("xform", instance.xform)
        instance.username = validated_data.get("username", instance.username)
        instance.role = validated_data.get("role", instance.role)
        instance.save()

        return instance

    # pylint: disable=unused-argument,no-self-use
    def create(self, validated_data):
        """Assign role permission for a form to a user."""
        instance = ShareXForm(**validated_data)
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

    # pylint: disable=no-self-use
    def validate_role(self, value):
        """check that the role exists"""
        if value not in ROLES:
            raise serializers.ValidationError(_(f"Unknown role '{value}'."))

        return value
