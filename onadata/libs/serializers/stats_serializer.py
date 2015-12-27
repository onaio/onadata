from django.utils.translation import ugettext as _
from rest_framework import exceptions
from rest_framework import serializers
from rest_framework.utils.serializer_helpers import ReturnList

from onadata.libs.data.statistics import\
    get_median_for_numeric_fields_in_form,\
    get_mean_for_numeric_fields_in_form,\
    get_mode_for_numeric_fields_in_form, get_min_max_range, get_all_stats
from onadata.apps.logger.models.xform import XForm
from onadata.libs.data.query import get_form_submissions_grouped_by_field

SELECT_FIELDS = ['select one', 'select multiple']

STATS_FUNCTIONS = {
    'mean': get_mean_for_numeric_fields_in_form,
    'median': get_median_for_numeric_fields_in_form,
    'mode': get_mode_for_numeric_fields_in_form,
    'range': get_min_max_range
}


class SubmissionStatsSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='submissionstats-detail', lookup_field='pk')

    class Meta:
        model = XForm
        fields = ('id', 'id_string', 'url')


class SubmissionStatsInstanceSerializer(serializers.Serializer):
    def to_representation(self, obj):
        if obj is None:
            return super(SubmissionStatsInstanceSerializer, self)\
                .to_representation(obj)

        request = self.context.get('request')
        field = request.query_params.get('group')
        name = request.query_params.get('name', field)

        if field is None:
            raise exceptions.ParseError(_(u"Expecting `group` and `name`"
                                          u" query parameters."))

        try:
            data = get_form_submissions_grouped_by_field(
                obj, field, name)
        except ValueError as e:
            raise exceptions.ParseError(detail=e.message)
        else:
            if data:
                element = obj.get_survey_element(field)

                if element and element.type in SELECT_FIELDS:
                    for record in data:
                        label = obj.get_choice_label(element, record[name])
                        record[name] = label

        return data

    @property
    def data(self):
        ret = super(serializers.Serializer, self).data

        return ReturnList(ret, serializer=self)


class StatsSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='stats-detail', lookup_field='pk')

    class Meta:
        model = XForm
        fields = ('id', 'id_string', 'url')


class StatsInstanceSerializer(serializers.Serializer):
    def to_representation(self, obj):
        if obj is None:
            return super(StatsInstanceSerializer, self).to_representation(obj)

        request = self.context.get('request')
        method = request.query_params.get('method', None)
        field = request.query_params.get('field', None)

        if field and field not in obj.get_keys():
            raise exceptions.ParseError(detail=_("Field not in XForm."))

        stats_function = STATS_FUNCTIONS.get(method and method.lower(),
                                             get_all_stats)

        try:
            data = stats_function(obj, field)
        except ValueError as e:
            raise exceptions.ParseError(detail=e.message)

        return data
