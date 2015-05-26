from rest_framework import serializers
from rest_framework.exceptions import ParseError
from onadata.apps.logger.models.project import Project


class ProjectField(serializers.WritableField):
    def to_native(self, obj):
        return obj.pk

    def from_native(self, data):
        try:
            project = Project.objects.get(pk=data)
        except Project.DoesNotExist:
            project = data
        except ValueError as e:
            raise ParseError(unicode(e))
        return project
