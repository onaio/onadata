from onadata.apps.logger.models import Project
from rest_framework import serializers


class ProjectRelatedField(serializers.RelatedField):
    """A custom field to represent the content_object generic relationship"""

    def get_attribute(self, instance):
        # xform is not an attribute of the MetaData object
        if instance:
            instance = instance.content_object

        return instance

    def to_internal_value(self, data):
        try:
            return Project.objects.get(id=data)
        except ValueError:
            raise Exception("project id should be an integer")

    def to_representation(self, instance):
        """Serialize project object"""
        if isinstance(instance, Project):
            return instance.id

        raise Exception("Project instance not found")
