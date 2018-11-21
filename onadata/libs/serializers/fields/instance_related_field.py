# -*- coding: utf-8 -*-
"""InstanceRelatedField"""
from rest_framework import serializers
from rest_framework.fields import SkipField

from onadata.apps.logger.models import Instance
from onadata.libs.serializers.fields.utils import get_object_id_by_content_type


class InstanceRelatedField(serializers.RelatedField):
    """A custom field to represent the content_object generic relationship"""

    def get_attribute(self, instance):
        val = get_object_id_by_content_type(instance, Instance)
        if val:
            return val

        raise SkipField()

    def to_internal_value(self, data):
        try:
            return Instance.objects.get(pk=data)
        except ValueError:
            raise Exception("instance id should be an integer")

    def to_representation(self, value):
        """Serialize instance object"""
        return value
