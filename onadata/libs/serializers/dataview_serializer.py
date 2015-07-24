from django.utils.translation import ugettext as _
from django.core.cache import cache

from rest_framework import serializers
from rest_framework.exceptions import ParseError

from onadata.libs.serializers.fields.json_field import JsonField
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.data_view import SUPPORTED_FILTERS
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.project import Project
from onadata.libs.utils.cache_tools import DATAVIEW_COUNT


class DataViewSerializer(serializers.HyperlinkedModelSerializer):
    dataviewid = serializers.Field(source='id')
    name = serializers.CharField(max_length=255, source='name')
    url = serializers.HyperlinkedIdentityField(view_name='dataviews-detail',
                                               lookup_field='pk')
    xform = serializers.HyperlinkedRelatedField(
        view_name='xform-detail', lookup_field='pk',
        queryset=XForm.objects.all()
    )
    project = serializers.HyperlinkedRelatedField(
        view_name='project-detail', lookup_field='pk',
        queryset=Project.objects.all()
    )
    columns = JsonField(source='columns')
    query = JsonField(source='query', required=False)
    count = serializers.SerializerMethodField("get_data_count")
    instances_with_geopoints = \
        serializers.SerializerMethodField('check_instances_with_geopoints')

    class Meta:
        model = DataView

    def validate_query(self, attrs, source):
        query = attrs.get('query')

        if query:
            for q in query:
                if 'column' not in q:
                    raise serializers.ValidationError(_(
                        u"`column` not set in query"
                    ))

                if 'filter' not in q:
                    raise serializers.ValidationError(_(
                        u"`filter` not set in query"
                    ))

                if 'value' not in q:
                    raise serializers.ValidationError(_(
                        u"`value` not set in query"
                    ))

                comp = q.get('filter')

                if comp not in SUPPORTED_FILTERS:
                    raise serializers.ValidationError(_(
                        u"Filter not supported"
                    ))

        return attrs

    def validate_columns(self, attrs, source):
        columns = attrs.get('columns')

        if not isinstance(columns, list):
            raise serializers.ValidationError(_(
                u"`columns` should be a list of columns"
            ))

        return attrs

    def get_data_count(self, obj):
        if obj:
            count = cache.get('{}{}'.format(DATAVIEW_COUNT, obj.xform.pk))

            if count:
                return count

            count = DataView.query_data(obj, count=True)
            if 'error' in count:
                raise ParseError(count.get('error'))

            if 'count' in count[0]:
                count = count[0].get('count')
                cache.set('{}{}'.format(DATAVIEW_COUNT, obj.xform.pk),
                          count)

                return count
        return None

    def check_instances_with_geopoints(self, obj):

        if obj:
            check_geo = obj.has_geo_columnn_n_data()
            if obj.instances_with_geopoints != check_geo:
                obj.instances_with_geopoints = check_geo
                obj.save()
            return obj.instances_with_geopoints
        return False
