# -*- coding: utf-8 -*-
"""
Share projects to team functions.
"""
from django.utils.translation import gettext as _

from rest_framework import serializers

from onadata.libs.models.share_team_project import ShareTeamProject
from onadata.libs.permissions import ROLES
from onadata.libs.serializers.fields.project_field import ProjectField
from onadata.libs.serializers.fields.team_field import TeamField


class ShareTeamProjectSerializer(serializers.Serializer):
    """Shares a project with a team."""

    team = TeamField()
    project = ProjectField()
    role = serializers.CharField(max_length=50)

    # pylint: disable=no-self-use
    def update(self, instance, validated_data):
        """Update project sharing properties."""
        instance.team = validated_data.get("team", instance.team)
        instance.project = validated_data.get("project", instance.project)
        instance.role = validated_data.get("role", instance.role)
        instance.save()

        return instance

    # pylint: disable=no-self-use
    def create(self, validated_data):
        """Shares a project to a team."""
        instance = ShareTeamProject(**validated_data)
        instance.save()

        return instance

    # pylint: disable=no-self-use
    def validate_role(self, value):
        """check that the role exists"""

        if value not in ROLES:
            raise serializers.ValidationError(_(f"Unknown role '{value}'."))

        return value


class RemoveTeamFromProjectSerializer(ShareTeamProjectSerializer):
    """Remove a team from a project."""

    remove = serializers.BooleanField()

    # pylint: disable=no-self-use
    def update(self, instance, validated_data):
        """Remove a team from a project"""
        instance.remove = validated_data.get("remove", instance.remove)
        instance.save()

        return instance

    # pylint: disable=no-self-use
    def create(self, validated_data):
        """Remove a team from a project"""
        instance = ShareTeamProject(**validated_data)
        instance.save()

        return instance
