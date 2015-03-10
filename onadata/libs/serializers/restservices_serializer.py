from rest_framework import serializers

from onadata.apps.restservice.models import RestService


class RestServiceSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='pk', read_only=True)
    xform = serializers.PrimaryKeyRelatedField()
    name = serializers.CharField(max_length=50)
    service_url = serializers.URLField(required=True)

    class Meta:
        model = RestService
