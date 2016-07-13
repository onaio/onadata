from onadata.apps.logger.models import XForm
from rest_framework import serializers
from rest_framework.fields import SkipField


class XFormRelatedField(serializers.RelatedField):
    """A custom field to represent the content_object generic relationship"""

    def get_attribute(self, instance):
        # xform is not an attribute of the MetaData object
        if instance and isinstance(instance.content_object, XForm):
            return instance.content_object

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
        return instance.pk
