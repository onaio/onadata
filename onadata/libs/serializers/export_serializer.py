from rest_framework import serializers
from onadata.apps.viewer.models.export import Export

class ExportSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Export
        fields = ('id', 'xform')
