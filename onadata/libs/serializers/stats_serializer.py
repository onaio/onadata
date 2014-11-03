from django.utils.translation import ugettext as _
from rest_framework import exceptions
from rest_framework import serializers

from onadata.apps.api.tools import (
    get_all_stats,
    get_mode_for_numeric_fields_in_form,
    get_mean_for_numeric_fields_in_form,
    get_median_for_numeric_fields_in_form, get_min_max_range
)
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
        lookup_field = 'pk'


class SubmissionStatsInstanceSerializer(serializers.Serializer):
    def to_native(self, obj):
        if obj is None:
            return \
                super(SubmissionStatsInstanceSerializer, self).to_native(obj)

        request = self.context.get('request')
        field = request.QUERY_PARAMS.get('group')
        name = request.QUERY_PARAMS.get('name', field)

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
                dd = obj.data_dictionary()
                element = dd.get_survey_element(field)

                if element and element.type in SELECT_FIELDS:
                    for record in data:
                        label = dd.get_choice_label(element, record[name])
                        record[name] = label

        return data


class StatsSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='stats-detail', lookup_field='pk')

    class Meta:
        model = XForm
        fields = ('id', 'id_string', 'url')
        lookup_field = 'pk'


class StatsInstanceSerializer(serializers.Serializer):
    def to_native(self, obj):
        if obj is None:
            return super(StatsInstanceSerializer, self).to_native(obj)

        request = self.context.get('request')
        method = request.QUERY_PARAMS.get('method', None)
        field = request.QUERY_PARAMS.get('field', None)

        if field and field not in obj.data_dictionary().get_keys():
            raise exceptions.ParseError(detail=_("Field not in XForm."))

        stats_function = STATS_FUNCTIONS.get(method and method.lower(),
                                             get_all_stats)

        try:
            data = stats_function(obj, field)
        except ValueError as e:
            raise exceptions.ParseError(detail=e.message)

        return data
