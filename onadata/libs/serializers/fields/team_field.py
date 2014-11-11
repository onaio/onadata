from rest_framework import serializers
from onadata.apps.api.models.team import Team


class TeamField(serializers.WritableField):
    def to_native(self, obj):
        return obj.pk

    def from_native(self, data):
        return Team.objects.get(pk=data)
