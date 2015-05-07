from django.core.validators import ValidationError
from django.utils.translation import ugettext as _

from rest_framework import serializers
from onadata.libs.models.share_team_project import ShareTeamProject
from onadata.libs.permissions import ROLES
from onadata.libs.serializers.fields.team_field import TeamField
from onadata.libs.serializers.fields.project_field import ProjectField


class ShareTeamProjectSerializer(serializers.Serializer):
    team = TeamField()
    project = ProjectField()
    role = serializers.CharField(max_length=50)

    def restore_object(self, attrs, instance=None):
        if instance is not None:
            instance.team = attrs.get('team', instance.team)
            instance.project = attrs.get('project', instance.project)
            instance.role = attrs.get('role', instance.role)

            return instance

        return ShareTeamProject(**attrs)

    def validate_role(self, attrs, source):
        """check that the role exists"""
        value = attrs[source]

        if value not in ROLES:
            raise ValidationError(_(u"Unknown role '%(role)s'."
                                    % {"role": value}))

        return attrs


class RemoveTeamFromProjectSerializer(ShareTeamProjectSerializer):
    remove = serializers.BooleanField()

    def restore_object(self, attrs, instance=None):
        if instance is not None:
            instance.remove = attrs.get('remove', instance.remove)

            return instance

        return ShareTeamProject(**attrs)
