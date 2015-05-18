from rest_framework import serializers

from onadata.libs.serializers.fields.json_field import JsonField
from onadata.apps.logger.models.data_view import DataView


class DataViewSerializer(serializers.HyperlinkedModelSerializer):

    name = serializers.CharField(max_length=255, source='name')
    url = serializers.HyperlinkedIdentityField(view_name='dataview-detail',
                                               lookup_field='pk')
    xform = serializers.HyperlinkedRelatedField(view_name='xform-detail',
                                                source='xform',
                                                lookup_field='pk')
    project = serializers.HyperlinkedRelatedField(view_name='project-detail',
                                                  source='project',
                                                  lookup_field='pk')
    columns = JsonField(source='columns')
    query = JsonField(source='query')

    class Meta:
        model = DataView
