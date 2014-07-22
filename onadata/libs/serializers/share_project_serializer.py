from django.core.validators import ValidationError
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from rest_framework import serializers
from onadata.libs.models.share_project import ShareProject
from onadata.libs.permissions import ROLES
from onadata.libs.serializers.fields.project_field import ProjectField


class ShareProjectSerializer(serializers.Serializer):
    project = ProjectField()
    username = serializers.CharField(max_length=255)
    role = serializers.CharField(max_length=50)

    def restore_object(self, attrs, instance=None):
        if instance is not None:
            instance.project = attrs.get('project', instance.project)
            instance.username = attrs.get('username', instance.username)
            instance.role = attrs.get('role', instance.role)

            return instance

        return ShareProject(**attrs)

    def validate_username(self, attrs, source):
        """Check that the username exists"""
        value = attrs[source]
        try:
            User.objects.get(username=value)
        except User.DoesNotExist:
            raise ValidationError(_(u"User '%(value)s' does not exist."
                                    % {"value": value}))

        return attrs

    def validate_role(self, attrs, source):
        """check that the role exists"""
        value = attrs[source]

        if value not in ROLES:
            raise ValidationError(_(u"Unknown role '%(role)s'."
                                    % {"role": value}))

        return attrs

    def remove_user(self):
        self.object.remove_user()
