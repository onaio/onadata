from rest_framework import serializers
from rest_framework.exceptions import ParseError
from django.core.validators import ValidationError
from django.utils.translation import ugettext as _
from onadata.apps.logger.models.project import Project


class ProjectField(serializers.WritableField):
    def to_native(self, obj):
        return obj.pk

    def from_native(self, data):
        if data is not None:
            try:
                project = Project.objects.get(pk=data)
            except Project.DoesNotExist:
                raise ValidationError(
                    _(u"Project with id '%(value)s' does not exist." %
                        {"value": data}))
            except ValueError as e:
                raise ParseError(unicode(e))
            return project
