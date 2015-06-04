from rest_framework import serializers
from generic_relations.relations import GenericRelatedField

from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.widget import Widget

class WidgetSerializer(serializers.HyperlinkedModelSerializer):
    #url = serializers.HyperlinkedIdentityField(view_name='widgets-detail',
    #                                           lookup_field='pk')
    key = serializers.CharField(max_length=255, source='key', read_only=True)
    title = serializers.CharField(max_length=255, source='title', required=False)
    description = serializers.CharField(max_length=255, source='description', required=False)

    widget_type = serializers.ChoiceField(choices=Widget.WIDGETS_TYPES,
                                          source='widget_type')
    view_type = serializers.CharField(max_length=50, source='view_type')
    column = serializers.CharField(max_length=50, source='column')
    group_by = serializers.CharField(max_length=50, source='group_by',
                                     required=False)

    content_object = GenericRelatedField({
        XForm: serializers.HyperlinkedRelatedField(view_name='xform-detail',
                                                   lookup_field='pk'),
        DataView: serializers.HyperlinkedRelatedField(
            view_name='dataviews-detail', lookup_field='pk'),
    })

    class Meta:
        model = Widget
        fields = ('key', 'title', 'description', 'widget_type', 'view_type',
                  'column', 'group_by', 'content_object')

