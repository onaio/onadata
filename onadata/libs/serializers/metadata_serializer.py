from rest_framework import serializers

from onadata.apps.main.models import MetaData


class MetaDataSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = MetaData
