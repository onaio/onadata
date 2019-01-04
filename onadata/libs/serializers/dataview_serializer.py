import datetime

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
from onadata.libs.utils.common_tags import MONGO_STRFTIME, DATE_FORMAT
from onadata.libs.utils.model_tools import get_columns_with_hxl
from onadata.libs.utils.api_export_tools import include_hxl_row


LAST_SUBMISSION_TIME = '_submission_time'


def validate_date(value):
    try:
        datetime.datetime.strptime(value, DATE_FORMAT)
        return True
    except ValueError:
        return False


def validate_datetime(value):
    try:
        datetime.datetime.strptime(value, MONGO_STRFTIME)
        return True
    except ValueError:
        return False


def match_columns(data, instance=None):
    matches_parent = data.get('matches_parent')
    xform = data.get('xform', instance.xform if instance else None)
    columns = data.get('columns', instance.columns if instance else None)
    if xform and columns:
        fields = xform.get_field_name_xpaths_only()
        matched = [col for col in columns if col in fields]
        matches_parent = len(matched) == len(columns) == len(fields)
        data['matches_parent'] = matches_parent

    return data


class DataViewMinimalSerializer(serializers.HyperlinkedModelSerializer):
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
    matches_parent = serializers.BooleanField(default=True)

    class Meta:
        model = DataView
        fields = ('dataviewid', 'name', 'url', 'xform', 'project', 'columns',
                  'query', 'matches_parent', 'date_created',
                  'instances_with_geopoints', 'date_modified')


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
    has_hxl_support = serializers.SerializerMethodField()

    class Meta:
        model = DataView
        fields = ('dataviewid', 'name', 'xform', 'project', 'columns', 'query',
                  'matches_parent', 'count', 'instances_with_geopoints',
                  'last_submission_time', 'has_hxl_support', 'url',
                  'date_created', 'deleted_at', 'deleted_by')
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=DataView.objects.all(),
                fields=('name', 'xform')
            )
        ]

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

    def validate(self, attrs):
        if 'xform' in attrs and attrs.get('xform'):
            xform = attrs.get('xform')
            know_dates = [e.name for e in
                          xform.get_survey_elements_of_type('date')]
            know_dates.append('_submission_time')
            for q in attrs.get('query', []):
                column = q.get('column')
                value = q.get('value')

                if column in know_dates and not \
                        (validate_datetime(value) or validate_date(value)):
                    raise serializers.ValidationError(_(
                        u"Date value in {} should be yyyy-mm-ddThh:m:s or "
                        u"yyyy-mm-dd"
                        .format(column)
                    ))

        return super(DataViewSerializer, self).validate(attrs)

    def get_count(self, obj):
        if obj:
            count_dict = cache.get('{}{}'.format(DATAVIEW_COUNT, obj.xform.pk))

            if count_dict:
                if obj.pk in count_dict:
                    return count_dict.get(obj.pk)
            else:
                count_dict = {}

            count_rows = DataView.query_data(obj, count=True)
            if 'error' in count_rows:
                raise ParseError(count_rows.get('error'))

            count_row = count_rows[0]
            if 'count' in count_row:
                count = count_row.get('count')
                count_dict.setdefault(obj.pk, count)
                cache.set('{}{}'.format(DATAVIEW_COUNT, obj.xform.pk),
                          count_dict)

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

    def get_has_hxl_support(self, obj):
        columns_with_hxl = get_columns_with_hxl(
            obj.xform.survey.get('children')
        )

        return include_hxl_row(obj.columns, list(columns_with_hxl))
