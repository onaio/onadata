# -*- coding: utf-8 -*-
"""
The TeamSerializer class - access and update Team model objects.
"""
from django.contrib.auth import get_user_model

from rest_framework import serializers

from onadata.apps.api.models import OrganizationProfile, Team
from onadata.apps.logger.models import Project
from onadata.libs.permissions import get_team_project_default_permissions
from onadata.libs.serializers.fields.hyperlinked_multi_identity_field import (
    HyperlinkedMultiIdentityField,
)
from onadata.libs.serializers.user_serializer import UserSerializer

User = get_user_model()


class TeamSerializer(serializers.Serializer):
    """
    The TeamSerializer class - access and update Team model objects.
    """

    teamid = serializers.ReadOnlyField(source="id")
    url = HyperlinkedMultiIdentityField(view_name="team-detail")
    name = serializers.CharField(max_length=100, source="team_name", required=True)
    organization = serializers.SlugRelatedField(
        slug_field="username",
        queryset=User.objects.filter(pk__in=OrganizationProfile.objects.values("user")),
    )
    projects = serializers.SerializerMethodField()
    users = serializers.SerializerMethodField()

    def get_users(self, obj):
        """Returns a users in a team."""
        users = []

        if obj:
            for user in obj.user_set.filter(is_active=True):
                users.append(UserSerializer(instance=user).data)

        return users

    def get_projects(self, obj):
        """Organization Projects with default role"""
        projects = []

        if obj:
            for project in Project.objects.filter(organization__id=obj.organization.id):
                project_map = {}
                project_map["name"] = project.name
                project_map["projectid"] = project.pk
                project_map["default_role"] = get_team_project_default_permissions(
                    obj, project
                )
                projects.append(project_map)

        return projects

    def update(self, instance, validated_data):
        org = validated_data.get("organization", None)
        projects = validated_data.get("projects", [])

        instance.organization = org if org else instance.organization
        instance.name = validated_data.get("team_name", instance.name)
        instance.projects.clear()

        for project in projects:
            instance.projects.add(project)

        instance.save()

        return instance

    def create(self, validated_data):
        org = validated_data.get("organization", None)
        team_name = validated_data.get("team_name", None)
        request = self.context.get("request")
        created_by = request.user

        return Team.objects.create(
            organization=org, name=team_name, created_by=created_by
        )
