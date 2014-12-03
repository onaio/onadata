from django.core.validators import ValidationError
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from rest_framework import serializers
from onadata.libs.models.share_project import ShareProject
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

    def remove_user_validation(self):
        # Check and confirm that the project will be left with at least one
        # owner.
        if self.object.role == OwnerRole.name:
            results = get_object_users_with_permissions(self.object.project)

            # count all the owners
            count = 0
            for r in results:
                if r.get('role') == OwnerRole.name:
                    count += 1
            status = u"Project cannot be without an owner"\
                if count == 1 else u"Ok"

            return {"status": status}
        else:
            return {"status": u"Ok"}

    def remove_user(self):
        self.object.remove_user()
