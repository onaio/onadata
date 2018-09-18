from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache

from rest_framework import serializers
from rest_framework.fields import SkipField

from onadata.apps.logger.models import Instance


class InstanceRelatedField(serializers.RelatedField):
    """A custom field to represent the content_object generic relationship"""

    def get_attribute(self, instance):
        content_type_id = cache.get("instance_content_type_id")
        if not content_type_id:
            try:
                content_type_id = ContentType.objects.get(
                    app_label="logger", model="instance"
                ).id
            except ContentType.DoesNotExist:
                pass
            else:
                cache.set("instance_content_type_id", content_type_id)
        if not content_type_id:
            if instance and isinstance(instance.content_object, Instance):
                return instance.object_id
        else:
            if instance and instance.content_type_id == content_type_id:
                return instance.object_id

        raise SkipField()

    def to_internal_value(self, data):
        try:
            return Instance.objects.get(pk=data)
        except ValueError:
            raise Exception("project id should be an integer")

    def to_representation(self, instance):
        """Serialize project object"""
        return instance
