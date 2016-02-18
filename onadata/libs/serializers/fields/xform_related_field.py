from onadata.apps.logger.models import XForm
from rest_framework import serializers


class XFormRelatedField(serializers.RelatedField):
    """A custom field to represent the content_object generic relationship"""

    def get_attribute(self, instance):
        # xform is not an attribute of the MetaData object
        if instance:
            instance = instance.content_object

        return instance

    def to_internal_value(self, data):
        try:
            return XForm.objects.get(id=data)
        except ValueError:
            raise Exception("xform id should be an integer")

    def to_representation(self, instance):
        """Serialize xform object"""
        if isinstance(instance, XForm):
            return instance.id

        raise Exception("XForm instance not found")
