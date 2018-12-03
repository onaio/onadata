# -*- coding: utf-8 -*-
"""XFormRelatedField"""

from rest_framework import serializers
from rest_framework.fields import SkipField

from onadata.apps.logger.models import XForm
from onadata.libs.serializers.fields.utils import get_object_id_by_content_type


class XFormRelatedField(serializers.RelatedField):
    """A custom field to represent the content_object generic relationship"""

    def get_attribute(self, instance):
        val = get_object_id_by_content_type(instance, XForm)
        if val:
            return val

        raise SkipField()

    def to_internal_value(self, data):
        try:
            return XForm.objects.get(id=data)
        except ValueError:
            raise serializers.ValidationError("xform id should be an integer")
        except XForm.DoesNotExist:
            raise serializers.ValidationError("XForm does not exist")

    def to_representation(self, value):
        """Serialize xform object"""
        return value
