# -*- coding: utf-8 -*-
"""
Stats API endpoint serializer.
"""
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext as _

from rest_framework import exceptions, serializers
from rest_framework.utils.serializer_helpers import ReturnList

from onadata.apps.logger.models.xform import XForm
from onadata.libs.data.query import get_form_submissions_grouped_by_field
from onadata.libs.data.statistics import (
    get_all_stats,
    get_mean_for_numeric_fields_in_form,
    get_median_for_numeric_fields_in_form,
    get_min_max_range,
    get_mode_for_numeric_fields_in_form,
)
from onadata.libs.utils.cache_tools import XFORM_SUBMISSION_STAT

SELECT_FIELDS = ["select one", "select multiple"]

STATS_FUNCTIONS = {
    "mean": get_mean_for_numeric_fields_in_form,
    "median": get_median_for_numeric_fields_in_form,
    "mode": get_mode_for_numeric_fields_in_form,
    "range": get_min_max_range,
}


class SubmissionStatsSerializer(serializers.HyperlinkedModelSerializer):
    """Submission stats serializer for use with the list API endpoint, summary of the
    submission stats endpoints."""

    url = serializers.HyperlinkedIdentityField(
        view_name="submissionstats-detail", lookup_field="pk"
    )

    class Meta:
        model = XForm
        fields = ("id", "id_string", "url")


# pylint: disable=abstract-method
class SubmissionStatsInstanceSerializer(serializers.Serializer):
    """Submissions stats instance serializer - provides submission summary stats."""

    def to_representation(self, instance):
        """Returns submissions stats grouped by a specified field."""
        if instance is None:
            return super().to_representation(instance)

        request = self.context.get("request")
        field = request.query_params.get("group")
        name = request.query_params.get("name", field)

        if field is None:
            raise exceptions.ParseError(
                _("Expecting `group` and `name` query parameters.")
            )

        cache_key = f"{XFORM_SUBMISSION_STAT}{instance.pk}{field}{name}"

        data = cache.get(cache_key)
        if data:
            return data

        try:
            data = get_form_submissions_grouped_by_field(instance, field, name)
        except ValueError as error:
            raise exceptions.ParseError(detail=error)
        if data:
            element = instance.get_survey_element(field)

            if element and element.type in SELECT_FIELDS:
                for record in data:
                    label = instance.get_choice_label(element, record[name])
                    record[name] = label

        cache.set(cache_key, data, settings.XFORM_SUBMISSION_STAT_CACHE_TIME)

        return data

    @property
    def data(self):
        """Return the data as a list with ReturnList instead of a python object."""
        ret = super(serializers.Serializer, self).data

        return ReturnList(ret, serializer=self)


class StatsSerializer(serializers.HyperlinkedModelSerializer):
    """Stats serializer for use with the list API endpoint, summary of the stats
    endpoints."""

    url = serializers.HyperlinkedIdentityField(
        view_name="stats-detail", lookup_field="pk"
    )

    class Meta:
        model = XForm
        fields = ("id", "id_string", "url")


# pylint: disable=abstract-method
class StatsInstanceSerializer(serializers.Serializer):
    """The stats instance serializer - calls the relevant statistical functions and
    returns the results against form data submissions."""

    def to_representation(self, instance):
        """Returns the result of the selected stats function."""
        if instance is None:
            return super().to_representation(instance)

        request = self.context.get("request")
        method = request.query_params.get("method", None)
        field = request.query_params.get("field", None)

        if field and field not in instance.get_keys():
            raise exceptions.ParseError(detail=_("Field not in XForm."))

        stats_function = STATS_FUNCTIONS.get(method and method.lower(), get_all_stats)

        try:
            data = stats_function(instance, field)
        except ValueError as error:
            raise exceptions.ParseError(detail=error)

        return data
