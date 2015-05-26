from django.core.validators import ValidationError
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from rest_framework import serializers
from onadata.libs.models.clone_xform import CloneXForm
from onadata.libs.serializers.fields.xform_field import XFormField
from onadata.libs.serializers.fields.project_field import ProjectField
from onadata.apps.logger.models.project import Project


class CloneXFormSerializer(serializers.Serializer):
    xform = XFormField()
    username = serializers.CharField(max_length=255)
    project = ProjectField(required=False)

    def restore_object(self, attrs, instance=None):
        if instance is not None:
            instance.xform = attrs.get('xform', instance.xform)
            instance.username = attrs.get('username', instance.username)
            instance.project = attrs.get('project', instance.project)

            return instance

        return CloneXForm(**attrs)

    def validate_username(self, attrs, source):
        """Check that the username exists"""
        value = attrs[source]
        try:
            User.objects.get(username=value)
        except User.DoesNotExist:
            raise ValidationError(_(u"User '%(value)s' does not exist."
                                    % {"value": value}))

        return attrs

    def validate_project(self, attrs, source):
        """Check that projects exists"""
        value = attrs[source]
        if value is not None and not isinstance(value, Project):
            try:
                Project.objects.get(pk=int(value))
            except Project.DoesNotExist:
                raise ValidationError(
                    _(u"Project with id '%(value)s' does not exist." %
                        {"value": value}))
        return attrs
