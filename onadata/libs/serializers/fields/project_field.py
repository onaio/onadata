# -*- coding: utf-8 -*-
"""
ProjectField serializer field.
"""
from django.utils.translation import gettext as _

from rest_framework import serializers

from onadata.apps.logger.models.project import Project


class ProjectField(serializers.Field):
    """Project field for use with a Project object/instance."""

    def to_representation(self, value):
        """Returns the project pk."""
        return value.pk

    def to_internal_value(self, data):
        """Validates that a project exists."""
        if data is not None:
            try:
                project = Project.objects.get(pk=data)
            except Project.DoesNotExist as error:
                raise serializers.ValidationError(
                    _(f"Project with id '{data}' does not exist.")
                ) from error
            except ValueError as error:
                raise serializers.ValidationError(str(error)) from error

            return project
        return data
