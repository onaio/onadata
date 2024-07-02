# -*- coding: utf-8 -*-
"""InstanceRelatedField"""
from rest_framework import serializers
from rest_framework.fields import SkipField

from onadata.apps.logger.models import Instance
from onadata.libs.serializers.fields.utils import get_object_id_by_content_type


class InstanceRelatedField(serializers.RelatedField):
    """A custom field to represent the content_object generic relationship"""

    def get_attribute(self, instance):
        """Returns instance pk."""
        val = get_object_id_by_content_type(instance, Instance)
        if val:
            return val

        raise SkipField()

    def to_internal_value(self, data):
        """Validates if the instance exists."""
        try:
            return Instance.objects.get(pk=data)
        except ValueError as error:
            raise ValueError("instance id should be an integer") from error

    def to_representation(self, value):
        """Serialize instance object"""
        return value
