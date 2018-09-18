from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache

from rest_framework import serializers
from rest_framework.fields import SkipField

from onadata.apps.logger.models import XForm


class XFormRelatedField(serializers.RelatedField):
    """A custom field to represent the content_object generic relationship"""

    def get_attribute(self, instance):
        # xform is not an attribute of the MetaData object
        content_type_id = cache.get("xform_content_type_id")
        if not content_type_id:
            try:
                content_type_id = ContentType.objects.get(
                    app_label="logger", model="xform"
                ).id
            except ContentType.DoesNotExist:
                pass
            else:
                cache.set("xform_content_type_id", content_type_id)
        if not content_type_id:
            if instance and isinstance(instance.content_object, XForm):
                return instance.object_id
        else:
            if instance and instance.content_type_id == content_type_id:
                return instance.object_id

        raise SkipField()

    def to_internal_value(self, data):
        try:
            return XForm.objects.get(id=data)
        except ValueError:
            raise serializers.ValidationError("xform id should be an integer")
        except XForm.DoesNotExist:
            raise serializers.ValidationError("XForm does not exist")

    def to_representation(self, instance):
        """Serialize xform object"""
        return instance
