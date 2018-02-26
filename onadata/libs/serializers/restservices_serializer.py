from rest_framework import serializers

from onadata.apps.logger.models import XForm
from onadata.apps.restservice.models import RestService


class RestServiceSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='pk', read_only=True)
    xform = serializers.PrimaryKeyRelatedField(
        queryset=XForm.objects.all()
    )
    name = serializers.CharField(max_length=50)
    service_url = serializers.URLField(required=True)

    class Meta:
        model = RestService
        fields = ('id', 'xform', 'name', 'service_url', 'date_created',
                  'date_modified', 'active', 'inactive_reason')
