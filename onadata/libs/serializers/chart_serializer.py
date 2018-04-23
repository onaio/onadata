from past.builtins import basestring

from django.http import Http404

from rest_framework import serializers

from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.chart_tools import build_chart_data_for_field
from onadata.libs.utils.common_tags import INSTANCE_ID


class ChartSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='chart-detail', lookup_field='pk')

    class Meta:
        model = XForm
        fields = ('id', 'id_string', 'url')


class FieldsChartSerializer(serializers.ModelSerializer):

    class Meta:
        model = XForm

    def to_representation(self, obj):
        data = {}
        request = self.context.get('request')

        if obj is not None:
            fields = obj.survey_elements

            if request:
                selected_fields = request.query_params.get('fields')

                if isinstance(selected_fields, basestring) \
                        and selected_fields != 'all':
                    fields = selected_fields.split(',')
                    fields = [e for e in obj.survey_elements
                              if e.name in fields]

                    if len(fields) == 0:
                        raise Http404(
                            "Field %s does not not exist on the form" % fields)

            for field in fields:
                if field.name == INSTANCE_ID:
                    continue
                field_data = build_chart_data_for_field(obj, field)
                data[field.name] = field_data

        return data
