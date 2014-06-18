from rest_framework import serializers

from onadata.apps.logger.models.xform import XForm


class ChartSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='chart-detail', lookup_field='pk')

    class Meta:
        model = XForm
        fields = ('id', 'id_string', 'url')
        lookup_field = 'pk'
