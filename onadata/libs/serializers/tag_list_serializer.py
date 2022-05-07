# -*- coding: utf-8 -*-
"""Tags list serializer module."""
from django.utils.translation import gettext as _

from rest_framework import serializers


class TagListSerializer(serializers.Field):
    """Tags serializer - represents tags as a list of strings."""

    def to_internal_value(self, data):
        """Validates the data is a list."""
        if isinstance(data, list):
            return data

        raise serializers.ValidationError(_("expected a list of data"))

    def to_representation(self, value):
        """Returns all tags linked to the object ``value`` as a list."""
        if value is None:
            return super().to_representation(value)

        if not isinstance(value, list):
            return [tag.name for tag in value.all()]

        return value
