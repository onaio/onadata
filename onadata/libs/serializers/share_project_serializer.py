# -*- coding: utf-8 -*-
"""
The ShareProjectSerializer class - support sharing a project.
"""
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from rest_framework import serializers

from onadata.libs.models.share_project import ShareProject
from onadata.libs.permissions import ROLES, OwnerRole, get_object_users_with_permissions
from onadata.libs.serializers.fields.project_field import ProjectField
from onadata.libs.utils.project_utils import propagate_project_permissions_async

User = get_user_model()


def attrs_to_instance(attrs, instance):
    """Apply attributes into a class object from a dict."""
    instance.project = attrs.get("project", instance.project)
    instance.username = attrs.get("username", instance.username)
    instance.role = attrs.get("role", instance.role)
    instance.remove = attrs.get("remove", instance.remove)

    return instance


class ShareProjectSerializer(serializers.Serializer):
    """
    The ShareProjectSerializer class - support sharing a project.
    """

    project = ProjectField()
    username = serializers.CharField(required=True)
    role = serializers.CharField(max_length=50)

    def create(self, validated_data):
        created_instances = []

        for username in validated_data.pop("username").split(","):
            validated_data["username"] = username
            instance = ShareProject(**validated_data)
            instance.save()
            created_instances.append(instance)

        propagate_project_permissions_async.apply_async(
            args=[validated_data.get("project").id], countdown=30
        )
        return created_instances

    def update(self, instance, validated_data):
        instance = attrs_to_instance(validated_data, instance)
        instance.save()
        propagate_project_permissions_async.apply_async(
            args=[validated_data.get("project").id], countdown=30
        )

        return instance

    def validate(self, attrs):
        for username in attrs.get("username").split(","):
            user = User.objects.get(username=username)
            project = attrs.get("project")

            # check if the user is the owner of the project
            if user and project:
                if user == project.organization:
                    raise serializers.ValidationError(
                        {
                            "username": _(
                                f"Cannot share project with the owner ({user.username})"
                            )
                        }
                    )

        return attrs

    def validate_username(self, value):
        """Check that the username exists"""
        usernames = [u.strip() for u in value.split(",")]
        user = None
        non_existent_users = []
        inactive_users = []

        for username in usernames:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                non_existent_users.append(username)
            else:
                if not user.is_active:
                    inactive_users.append(username)

        if non_existent_users:
            non_existent_users = ", ".join(non_existent_users)
            raise serializers.ValidationError(
                _(f"The following user(s) does/do not exist: {non_existent_users}")
            )

        if inactive_users:
            inactive_users = ", ".join(inactive_users)
            raise serializers.ValidationError(
                _(f"The following user(s) is/are not active: {inactive_users}")
            )

        return (",").join(usernames)

    def validate_role(self, value):
        """check that the role exists"""
        if value not in ROLES:
            raise serializers.ValidationError(_(f"Unknown role '{value}'."))

        return value


class RemoveUserFromProjectSerializer(ShareProjectSerializer):
    """RemoveUserFromProjectSerializer class - removes a user's access to a project."""

    remove = serializers.BooleanField()

    def update(self, instance, validated_data):
        instance = attrs_to_instance(validated_data, instance)
        instance.save()
        propagate_project_permissions_async.apply_async(
            args=[validated_data.get("project").id], countdown=30
        )

        return instance

    def create(self, validated_data):
        instance = ShareProject(**validated_data)
        instance.save()
        propagate_project_permissions_async.apply_async(
            args=[validated_data.get("project").id], countdown=30
        )

        return instance

    def validate(self, attrs):
        """Check and confirm that the project will be left with at least one
        owner. Raises a validation error if only one owner found"""

        if attrs.get("role") == OwnerRole.name:
            results = get_object_users_with_permissions(attrs.get("project"))

            # count all the owners
            count = len([res for res in results if res.get("role") == OwnerRole.name])

            if count <= 1:
                raise serializers.ValidationError(
                    {"remove": _("Project requires at least one owner")}
                )

        return attrs
