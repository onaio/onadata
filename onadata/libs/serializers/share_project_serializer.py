from django.core.validators import ValidationError
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from rest_framework import serializers
from onadata.libs.models.share_project import ShareProject
from onadata.apps.logger.models import Project
from onadata.libs.permissions import ROLES, get_object_users_with_permissions,\
    OwnerRole
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


class RemoveUserFromProjectSerializer(ShareProjectSerializer):
    remove = serializers.BooleanField()

    def restore_object(self, attrs, instance=None):
        if instance is not None:
            instance.project = attrs.get('project', instance.project)
            instance.username = attrs.get('username', instance.username)
            instance.role = attrs.get('role', instance.role)
            instance.remove = attrs.get('remove', instance.remove)
            return instance

        project = Project.objects.get(pk=self.init_data.get('project'))
        self.init_data['project'] = project
        return ShareProject(**self.init_data)

    def validate_remove(self, attrs, source):
        # Check and confirm that the project will be left with at least one
        # owner.

        if attrs.get('role') == OwnerRole.name:
            results = get_object_users_with_permissions(attrs.get('project'))

            # count all the owners
            count = len([res for res in results
                         if res.get('role') == OwnerRole.name])

            if count <= 1:
                raise ValidationError(
                    _(u"Project requires at least one owner"))
