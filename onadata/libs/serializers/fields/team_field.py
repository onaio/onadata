# -*- coding: utf-8 -*-
"""
The TeamField class.
"""
from rest_framework import serializers

from onadata.apps.api.models.team import Team


class TeamField(serializers.Field):
    """
    The TeamField class.
    """

    def to_representation(self, value):
        return value.pk

    def to_internal_value(self, data):
        return Team.objects.get(pk=data)
