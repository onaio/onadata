from rest_framework import serializers
from generic_relations.relations import GenericRelatedField

from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.widget import Widget
from onadata.libs.utils.string import str2bool


class WidgetSerializer(serializers.HyperlinkedModelSerializer):
    widgetid = serializers.Field(source='id')
    key = serializers.CharField(max_length=255, source='key', read_only=True)
    title = serializers.CharField(max_length=255, source='title',
                                  required=False)
    description = serializers.CharField(max_length=255, source='description',
                                        required=False)

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

    data = serializers.SerializerMethodField(
        'get_widget_data')

    class Meta:
        model = Widget
        fields = ('widgetid', 'key', 'title', 'description', 'widget_type',
                  'view_type', 'column', 'group_by', 'content_object', 'data')

    def get_widget_data(self, obj):
        # Get the request obj
        request = self.context.get('request')

        # Check if data flag is present
        data_flag = request.GET.get('data')
        key = request.GET.get('key')

        if (str2bool(data_flag) or key) and obj:
            data = Widget.query_data(obj)
        else:
            data = []
        return data
