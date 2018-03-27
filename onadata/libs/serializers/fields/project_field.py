from builtins import str as text
from django.utils.translation import ugettext as _
from rest_framework import serializers

from onadata.apps.logger.models.project import Project


class ProjectField(serializers.Field):
    def to_representation(self, obj):
        return obj.pk

    def to_internal_value(self, data):
        if data is not None:
            try:
                project = Project.objects.get(pk=data)
            except Project.DoesNotExist:
                raise serializers.ValidationError(_(
                    u"Project with id '%(value)s' does not exist." %
                    {"value": data}
                ))
            except ValueError as e:
                raise serializers.ValidationError(text(e))

            return project
