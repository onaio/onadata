# -*- coding: utf-8 -*-
"""
The OpenDataSerializer class - create/list OpenData model data.
"""

import collections

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404

from guardian.shortcuts import get_objects_for_user
from rest_framework import serializers

from onadata.apps.logger.models import OpenData, XForm


def get_manageable_xforms(user):
    """Return active XForms the user is allowed to change."""
    xforms = XForm.objects.filter(
        deleted_at__isnull=True,
        project__organization__is_active=True,
    )

    if (
        not user
        or not user.is_authenticated
        or user.username.casefold() == settings.ANONYMOUS_DEFAULT_USERNAME.casefold()
    ):
        return xforms.none()

    return get_objects_for_user(
        user,
        "logger.change_xform",
        klass=xforms,
        accept_global_perms=False,
    )


def get_data(request_data, update=False):
    """
    return a namedtuple with error, message and data values.
    """
    fields = ["object_id", "data_type", "name"]
    required_fields = ["object_id", "name"]
    results = collections.namedtuple("results", "error message data")
    if not update:
        if not set(required_fields).issubset(list(request_data)):
            return results(
                error=True,
                message="Fields object_id and name are required.",
                data=None,
            )

    fields.append("active")

    # check if invalid fields are provided
    if any(a not in fields for a in list(request_data)):
        return results(
            error=True,
            message="Valid fields are object_id, data_type and name.",
            data=None,
        )

    data = {}
    for key in fields:
        available = request_data.get(key) is not None
        if available:
            data.update({key: request_data.get(key)})

    return results(error=False, message=None, data=data)


class OpenDataSerializer(serializers.ModelSerializer):
    """
    The OpenDataSerializer class - create/list OpenData model data.
    """

    name = serializers.CharField(max_length=255, required=True)
    data_type = serializers.CharField(
        max_length=50,
        required=False,
        write_only=True,
    )
    object_id = serializers.IntegerField(required=False)
    active = serializers.BooleanField(required=False)

    class Meta:
        model = OpenData
        fields = ("name", "data_type", "object_id", "active")

    def validate_data_type(self, value):
        """OpenData capabilities are only supported for XForms."""
        if value != "xform":
            raise serializers.ValidationError("Only xform data is supported.")

        return value

    def _get_authorized_xform(self, object_id):
        """Resolve an XForm without revealing inaccessible object IDs."""
        request = self.context["request"]
        return get_object_or_404(
            get_manageable_xforms(request.user),
            id=object_id,
        )

    def create(self, validated_data):
        results = get_data(validated_data)
        if results.error:
            raise serializers.ValidationError(results.message)

        name = validated_data.get("name")
        object_id = validated_data.get("object_id")

        # Resolve and authorize the target before looking up an existing
        # capability. This prevents both unauthorized creation and UUID
        # disclosure through a pre-existing OpenData row.
        xform = self._get_authorized_xform(object_id)
        content_type = ContentType.objects.get_for_model(xform)

        open_data, _created = OpenData.objects.get_or_create(
            content_type=content_type,
            object_id=xform.id,
            defaults={"name": name},
        )

        return open_data

    def update(self, instance, validated_data):
        results = get_data(validated_data, update=True)
        if results.error:
            raise serializers.ValidationError(results.message)

        object_id = validated_data.get("object_id", instance.object_id)
        if object_id != instance.object_id:
            xform = self._get_authorized_xform(object_id)
            instance.content_type = ContentType.objects.get_for_model(xform)
            instance.object_id = xform.id

        instance.name = validated_data.get("name", instance.name)
        instance.active = validated_data.get("active", instance.active)
        instance.save()

        return instance


class OpenDataCreateSerializer(OpenDataSerializer):
    """Create serializer that returns a capability UUID once to its creator."""

    uuid = serializers.CharField(read_only=True)

    class Meta(OpenDataSerializer.Meta):
        fields = OpenDataSerializer.Meta.fields + ("uuid",)
