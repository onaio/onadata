from rest_framework import serializers

from onadata.apps.logger.models.data_view import DataView


class DataViewSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = DataView
