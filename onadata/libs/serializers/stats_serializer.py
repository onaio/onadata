from rest_framework import exceptions
from rest_framework import serializers

from onadata.apps.logger.models.xform import XForm
from onadata.libs.data.query import get_form_submissions_grouped_by_field

SELECT_FIELDS = ['select one', 'select multiple']


class SubmissionStatsSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='submissionstats-detail', lookup_field='pk')

    class Meta:
        model = XForm
        fields = ('id', 'id_string', 'url')
        lookup_field = 'pk'


class SubmissionStatsInstanceSerializer(serializers.Serializer):
    def to_native(self, obj):
        request = self.context.get('request')
        field = request.QUERY_PARAMS.get('group')
        name = request.QUERY_PARAMS.get('name', field)

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
