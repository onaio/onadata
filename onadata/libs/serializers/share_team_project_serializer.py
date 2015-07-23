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

    def update(self, instance, validated_data):
        instance.team = validated_data.get('team', instance.team)
        instance.project = validated_data.get('project', instance.project)
        instance.role = validated_data.get('role', instance.role)
        instance.save()

        return instance

    def create(self, validated_data):
        instance = ShareTeamProject(**validated_data)
        instance.save()

        return instance

    def validate_role(self, value):
        """check that the role exists"""

        if value not in ROLES:
            raise serializers.ValidationError(_(
                u"Unknown role '%(role)s'." % {"role": value}
            ))

        return value


class RemoveTeamFromProjectSerializer(ShareTeamProjectSerializer):
    remove = serializers.BooleanField()

    def update(self, instance, validated_data):
        instance.remove = validated_data.get('remove', instance.remove)
        instance.save()

        return instance

    def create(self, validated_data):
        instance = ShareTeamProject(**validated_data)
        instance.save()

        return instance
