from django.utils.translation import ugettext as _
from django.core.cache import cache

from rest_framework import serializers
from rest_framework.exceptions import ParseError

from onadata.libs.serializers.fields.json_field import JsonField
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.data_view import SUPPORTED_FILTERS
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.project import Project
from onadata.libs.utils.cache_tools import (
    DATAVIEW_COUNT,
    DATAVIEW_LAST_SUBMISSION_TIME)


LAST_SUBMISSION_TIME = '_submission_time'


def match_columns(data, instance=None):
    matches_parent = data.get('matches_parent')
    xform = data.get('xform', instance.xform if instance else None)
    columns = data.get('columns', instance.columns if instance else None)
    if xform and columns:
        dd = xform.data_dictionary()
        fields = [
            elem.get_abbreviated_xpath()
            for elem in dd.survey_elements
            if elem.type != '' and elem.type != 'survey'
        ]
        matched = [col for col in columns if col in fields]
        matches_parent = len(matched) == len(columns) == len(fields)
        data['matches_parent'] = matches_parent

    return data


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
    matches_parent = serializers.BooleanField(default=True)
    last_submission_time = serializers.SerializerMethodField()

    class Meta:
        model = DataView

    def create(self, validated_data):
        validated_data = match_columns(validated_data)

        return super(DataViewSerializer, self).create(validated_data)

    def update(self, instance, validated_data):
        validated_data = match_columns(validated_data, instance)

        return super(DataViewSerializer, self).update(instance, validated_data)

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

            count_rows = DataView.query_data(obj, count=True)
            if 'error' in count_rows:
                raise ParseError(count_rows.get('error'))

            count_row = count_rows[0]
            if 'count' in count_row:
                count = count_row.get('count')
                cache.set('{}{}'.format(DATAVIEW_COUNT, obj.xform.pk),
                          count)

                return count

        return None

    def get_last_submission_time(self, obj):
        if obj:
            last_submission_time = cache.get('{}{}'.format(
                DATAVIEW_LAST_SUBMISSION_TIME, obj.xform.pk))

            if last_submission_time:
                return last_submission_time

            last_submission_rows = DataView.query_data(
                obj, last_submission_time=True)  # data is returned as list

            if 'error' in last_submission_rows:
                raise ParseError(last_submission_rows.get('error'))

            if len(last_submission_rows):
                last_submission_row = last_submission_rows[0]

                if LAST_SUBMISSION_TIME in last_submission_row:
                    last_submission_time = last_submission_row.get(
                        LAST_SUBMISSION_TIME)
                    cache.set(
                        '{}{}'.format(
                            DATAVIEW_LAST_SUBMISSION_TIME, obj.xform.pk),
                        last_submission_time)

                return last_submission_time

        return None

    def get_instances_with_geopoints(self, obj):

        if obj:
            check_geo = obj.has_geo_columnn_n_data()
            if obj.instances_with_geopoints != check_geo:
                obj.instances_with_geopoints = check_geo
                obj.save()

            return obj.instances_with_geopoints

        return False
