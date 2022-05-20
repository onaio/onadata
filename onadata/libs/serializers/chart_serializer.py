# -*- coding: utf-8 -*-
"""
Chart serializer.
"""
from django.http import Http404

from rest_framework import serializers

from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.chart_tools import build_chart_data_for_field
from onadata.libs.utils.common_tags import INSTANCE_ID


# pylint: disable=too-many-public-methods
class ChartSerializer(serializers.HyperlinkedModelSerializer):
    """
    Chart serializer
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="chart-detail", lookup_field="pk"
    )

    class Meta:
        model = XForm
        fields = ("id", "id_string", "url")


# pylint: disable=too-many-public-methods
class FieldsChartSerializer(serializers.ModelSerializer):
    """
    Generate chart data for the field.
    """

    class Meta:
        model = XForm

    def to_representation(self, instance):
        """
        Generate chart data for a given field in the request query params.
        """
        data = {}
        request = self.context.get("request")

        if instance is not None:
            fields = instance.survey_elements

            if request:
                selected_fields = request.query_params.get("fields")

                if isinstance(selected_fields, str) and selected_fields != "all":
                    fields = selected_fields.split(",")
                    fields = [e for e in instance.survey_elements if e.name in fields]

                    if len(fields) == 0:
                        raise Http404(f"Field {fields} does not not exist on the form")

            for field in fields:
                if field.name == INSTANCE_ID:
                    continue
                field_data = build_chart_data_for_field(instance, field)
                data[field.name] = field_data

        return data
