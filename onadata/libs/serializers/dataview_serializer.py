# -*- coding: utf-8 -*-
"""
The DataViewSerializer - manage DataView objects.
"""

import datetime

from django.utils.translation import gettext as _

from rest_framework import serializers
from rest_framework.exceptions import ParseError, PermissionDenied

from onadata.apps.logger.models.data_view import (
    FILTERABLE_METADATA_COLUMNS,
    SUPPORTED_FILTERS,
    DataView,
)
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import XForm
from onadata.libs.permissions import CAN_VIEW_XFORM_DATA, ManagerRole
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.utils.api_export_tools import include_hxl_row
from onadata.libs.utils.cache_tools import (
    DATAVIEW_COUNT,
    DATAVIEW_LAST_SUBMISSION_TIME,
    safe_cache_get,
    safe_cache_set,
)
from onadata.libs.utils.common_tags import DATE_FORMAT, MONGO_STRFTIME
from onadata.libs.utils.dataview_filters import is_safe_column
from onadata.libs.utils.model_tools import get_columns_with_hxl

LAST_SUBMISSION_TIME = "_submission_time"


def validate_date(value):
    """Returns True if the ``value`` is a date string."""
    try:
        datetime.datetime.strptime(value, DATE_FORMAT)
    except ValueError:
        return False
    return True


def validate_datetime(value):
    """Returns True if the ``value`` is a datetime string."""
    try:
        datetime.datetime.strptime(value, MONGO_STRFTIME)
    except ValueError:
        return False
    return True


def _allowed_query_columns(xform):
    """Columns a DataView ``query`` filter may reference on ``xform``.

    Combines the form's own field XPaths with the submission metadata columns
    DataView filtering treats as first-class (``FILTERABLE_METADATA_COLUMNS``).
    Nested form XPaths (containing ``/``) are preserved because they are
    returned verbatim by the form; Django lookup separators such as ``__`` never
    appear here and are rejected separately by ``is_safe_column``.
    """
    return set(xform.get_field_name_xpaths_only()) | set(FILTERABLE_METADATA_COLUMNS)


def match_columns(data, instance=None):
    """Checks if the fields in two forms are a match."""
    xform = data.get("xform", instance.xform if instance else None)
    columns = data.get("columns", instance.columns if instance else None)
    if xform is not None and columns is not None:
        fields = set(xform.get_field_name_xpaths_only())
        data["matches_parent"] = set(columns) == fields

    return data


class DataViewMinimalSerializer(serializers.HyperlinkedModelSerializer):
    """
    The DataViewMinimalSerializer - manage DataView objects.
    """

    dataviewid = serializers.ReadOnlyField(source="id")
    name = serializers.CharField(max_length=255)
    url = serializers.HyperlinkedIdentityField(
        view_name="dataviews-detail", lookup_field="pk"
    )
    xform = serializers.HyperlinkedRelatedField(
        view_name="xform-detail", lookup_field="pk", queryset=XForm.objects.all()
    )
    project = serializers.HyperlinkedRelatedField(
        view_name="project-detail", lookup_field="pk", queryset=Project.objects.all()
    )
    columns = JsonField()
    query = JsonField(required=False)
    matches_parent = serializers.BooleanField(read_only=True)

    class Meta:
        model = DataView
        fields = (
            "dataviewid",
            "name",
            "url",
            "xform",
            "project",
            "columns",
            "query",
            "matches_parent",
            "date_created",
            "instances_with_geopoints",
            "date_modified",
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # This serializer is embedded in cached project/form responses, so it
        # must never cache a row-filter value that excluded-data readers could
        # later receive.
        representation["query"] = []
        return representation


class DataViewSerializer(serializers.HyperlinkedModelSerializer):
    """
    The DataViewSerializer - manage DataView objects.
    """

    dataviewid = serializers.ReadOnlyField(source="id")
    name = serializers.CharField(max_length=255)
    url = serializers.HyperlinkedIdentityField(
        view_name="dataviews-detail", lookup_field="pk"
    )
    xform = serializers.HyperlinkedRelatedField(
        view_name="xform-detail", lookup_field="pk", queryset=XForm.objects.all()
    )
    project = serializers.HyperlinkedRelatedField(
        view_name="project-detail", lookup_field="pk", queryset=Project.objects.all()
    )
    columns = JsonField()
    query = JsonField(required=False)
    count = serializers.SerializerMethodField()
    instances_with_geopoints = serializers.SerializerMethodField()
    matches_parent = serializers.BooleanField(read_only=True)
    last_submission_time = serializers.SerializerMethodField()
    has_hxl_support = serializers.SerializerMethodField()

    class Meta:
        model = DataView
        fields = (
            "dataviewid",
            "name",
            "xform",
            "project",
            "columns",
            "query",
            "matches_parent",
            "count",
            "instances_with_geopoints",
            "last_submission_time",
            "has_hxl_support",
            "url",
            "date_created",
        )
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=DataView.objects.all(), fields=("name", "xform")
            )
        ]

    def create(self, validated_data):
        validated_data = match_columns(validated_data)

        return super().create(validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        can_view_source_data = instance.xform.shared_data or (
            user is not None
            and user.is_authenticated
            and user.has_perm(CAN_VIEW_XFORM_DATA, instance.xform)
        )
        if not can_view_source_data:
            representation["query"] = []
        return representation

    def update(self, instance, validated_data):
        validated_data = match_columns(validated_data, instance)

        return super().update(instance, validated_data)

    def validate_query(self, value):
        """Checks if the query filters in ``value`` are known."""
        if value:
            for query in value:
                if "column" not in query:
                    raise serializers.ValidationError(_("`column` not set in query"))

                if "filter" not in query:
                    raise serializers.ValidationError(_("`filter` not set in query"))

                if "value" not in query:
                    raise serializers.ValidationError(_("`value` not set in query"))

                comp = query.get("filter")

                if comp not in SUPPORTED_FILTERS:
                    raise serializers.ValidationError(_("Filter not supported"))

        return value

    def validate_columns(self, value):
        """Checks the ``value`` is a list."""
        if not isinstance(value, list):
            raise serializers.ValidationError(
                _("`columns` should be a list of columns")
            )

        return value

    def validate_xform(self, value):
        """Prevent changing a DataView's source XForm after creation."""
        if self.instance is not None and value.pk != self.instance.xform_id:
            raise serializers.ValidationError(
                _("The source XForm of a DataView cannot be changed.")
            )

        return value

    def validate(self, attrs):
        self._validate_publication_authority(attrs)

        if "xform" in attrs and attrs.get("xform"):
            xform = attrs.get("xform")
            know_dates = [e.name for e in xform.get_survey_elements_of_type("date")]
            know_dates.append("_submission_time")
            for query in attrs.get("query", []):
                column = query.get("column")
                value = query.get("value")

                if column in know_dates and not (
                    validate_datetime(value) or validate_date(value)
                ):
                    raise serializers.ValidationError(
                        _(
                            "Date value in %(column)s should be yyyy-mm-ddThh:m:s "
                            "or yyyy-mm-dd"
                        )
                        % {"column": column}
                    )

        self._validate_query_columns(attrs)

        return super().validate(attrs)

    def _validate_publication_authority(self, attrs):
        """Require control of both sides of a filtered-data publication.

        A DataView project is an intentional access boundary and may differ
        from the source XForm project. Creating a DataView, or changing the
        destination, projection, or stored row filter, therefore publishes
        source data and requires manager-level authority over both the source
        XForm and destination project.
        """
        publication_fields = {"project", "columns", "query"}
        if self.instance is not None and publication_fields.isdisjoint(attrs):
            return

        request = self.context.get("request")
        user = getattr(request, "user", None)
        xform = attrs.get(
            "xform", self.instance.xform if self.instance is not None else None
        )
        project = attrs.get(
            "project", self.instance.project if self.instance is not None else None
        )
        has_required_objects = xform is not None and project is not None
        is_authenticated = user is not None and user.is_authenticated
        has_publication_roles = (
            has_required_objects
            and is_authenticated
            and ManagerRole.user_has_role(user, xform)
            and ManagerRole.user_has_role(user, project)
        )
        if not has_publication_roles:
            raise PermissionDenied(
                _(
                    "You must be a manager of both the source XForm and the "
                    "destination project."
                )
            )

    def _validate_query_columns(self, attrs):
        """Reject unsafe or unknown ``query`` columns for the target form.

        Each column must be a string free of the ORM lookup separator ``__``
        (``is_safe_column``) and must appear in the form's allow-list. Validates
        when the query is being set. An update that does not touch the query is
        left alone so a pre-existing legacy column does not fail an unrelated
        change. The source XForm is immutable after creation.
        """
        if "query" not in attrs:
            return

        xform = attrs.get("xform") or (
            self.instance.xform if self.instance is not None else None
        )
        if xform is None:
            return

        query = attrs.get("query")

        allowed_columns = _allowed_query_columns(xform)
        for query_item in query or []:
            column = query_item.get("column")
            if not is_safe_column(column):
                raise serializers.ValidationError(
                    {"query": _("Unsupported column '%(column)s'") % {"column": column}}
                )
            if column not in allowed_columns:
                raise serializers.ValidationError(
                    {"query": _("Unknown column '%(column)s'") % {"column": column}}
                )

    def get_count(self, obj):
        """Returns the submission count for the data view,"""
        if obj:
            count_dict = safe_cache_get(f"{DATAVIEW_COUNT}{obj.xform.pk}")

            if count_dict:
                if obj.pk in count_dict:
                    return count_dict.get(obj.pk)
            else:
                count_dict = {}

            count_rows = DataView.query_data(obj, count=True)
            if "error" in count_rows:
                raise ParseError(count_rows.get("error"))

            count_row = count_rows[0]
            if "count" in count_row:
                count = count_row.get("count")
                count_dict.setdefault(obj.pk, count)
                safe_cache_set(f"{DATAVIEW_COUNT}{obj.xform.pk}", count_dict)

                return count

        return None

    def get_last_submission_time(self, obj):
        """Returns the last submission timestamp."""
        if obj:
            last_submission_time = safe_cache_get(
                f"{DATAVIEW_LAST_SUBMISSION_TIME}{obj.xform.pk}"
            )

            if last_submission_time:
                return last_submission_time

            last_submission_rows = DataView.query_data(
                obj, last_submission_time=True
            )  # data is returned as list

            if "error" in last_submission_rows:
                raise ParseError(last_submission_rows.get("error"))

            if len(last_submission_rows):
                last_submission_row = last_submission_rows[0]

                if LAST_SUBMISSION_TIME in last_submission_row:
                    last_submission_time = last_submission_row.get(LAST_SUBMISSION_TIME)
                    safe_cache_set(
                        f"{DATAVIEW_LAST_SUBMISSION_TIME}{obj.xform.pk}",
                        last_submission_time,
                    )

                return last_submission_time

        return None

    def get_instances_with_geopoints(self, obj):
        """Returns True if a DataView has submissions with geopoints."""

        if obj:
            check_geo = obj.has_geo_columnn_n_data()
            if obj.instances_with_geopoints != check_geo:
                obj.instances_with_geopoints = check_geo
                obj.save()

            return obj.instances_with_geopoints

        return False

    def get_has_hxl_support(self, obj):
        """Returns true if a DataView has columns with HXL tags."""
        columns_with_hxl = get_columns_with_hxl(obj.xform.survey.get("children"))

        return include_hxl_row(obj.columns, list(columns_with_hxl))
