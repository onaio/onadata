from rest_framework import serializers
from onadata.apps.api.models.team import Team


class TeamField(serializers.Field):
    def to_representation(self, obj):
        return obj.pk

    def to_internal_value(self, data):
        return Team.objects.get(pk=data)
