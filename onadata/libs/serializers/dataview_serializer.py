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
    dataviewid = serializers.ReadOnlyField(source='id')
    name = serializers.CharField(max_length=255)
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
    columns = JsonField()
    query = JsonField(required=False)
    count = serializers.SerializerMethodField()
    instances_with_geopoints = serializers.SerializerMethodField()
    matches_parent = serializers.SerializerMethodField()

    class Meta:
        model = DataView

    def validate_query(self, value):
        if value:
            for q in value:
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

        return value

    def validate_columns(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(_(
                u"`columns` should be a list of columns"
            ))

        return value

    def get_count(self, obj):
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

    def get_instances_with_geopoints(self, obj):

        if obj:
            check_geo = obj.has_geo_columnn_n_data()
            if obj.instances_with_geopoints != check_geo:
                obj.instances_with_geopoints = check_geo
                obj.save()

            return obj.instances_with_geopoints

        return False

    def get_matches_parent(self, obj):
        if obj:
            # Get the parent xform data dictionary
            dd = obj.xform.data_dictionary()
            xform_columns = dd.get_mongo_field_names_dict().keys()
            if obj.xform.id_string in xform_columns:
                xform_columns.remove(obj.xform.id_string)
            dataview_columns = obj.columns
            # compare if the columns in the dataview match with parent
            matches_parent = set(xform_columns) == set(dataview_columns)

            if obj.matches_parent != matches_parent:
                obj.matches_parent = matches_parent
                obj.save()
            return obj.matches_parent

        return False
