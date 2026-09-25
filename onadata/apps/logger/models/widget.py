# -*- coding: utf-8 -*-
"""
Widget class module.
"""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from django.db.models import JSONField
from django.http import Http404

from ordered_model.models import OrderedModel

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.xform import XForm
from onadata.libs.data.query import (
    get_form_submissions_aggregated_by_select_one,
    get_form_submissions_grouped_by_field,
    get_form_submissions_grouped_by_select_one,
)
from onadata.libs.utils.chart_tools import (
    DATA_TYPE_MAP,
    FIELD_DATA_MAP,
    _flatten_multiple_dict_into_one,
    _use_labels_from_group_by_name,
    get_field_choices,
    get_field_label,
    resolve_field_xpath,
)
from onadata.libs.utils.common_tags import NUMERIC_LIST, SELECT_ONE, SUBMISSION_TIME
from onadata.libs.utils.common_tools import get_uuid


class Widget(OrderedModel):
    """
    Widget class - used for storing chart visual information.
    """

    CHARTS = "charts"

    # Other widgets types to be added later
    WIDGETS_TYPES = ((CHARTS, "Charts"),)

    # Will hold either XForm or DataView Model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    widget_type = models.CharField(max_length=25, choices=WIDGETS_TYPES, default=CHARTS)
    view_type = models.CharField(max_length=50)
    column = models.CharField(max_length=255)
    group_by = models.CharField(null=True, default=None, max_length=255, blank=True)

    title = models.CharField(null=True, default=None, max_length=255, blank=True)
    description = models.CharField(null=True, default=None, max_length=255, blank=True)
    aggregation = models.CharField(null=True, default=None, max_length=255, blank=True)
    key = models.CharField(db_index=True, unique=True, max_length=32)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    order_with_respect_to = "content_type"
    metadata = JSONField(default=dict, blank=True)

    class Meta(OrderedModel.Meta):
        app_label = "logger"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = get_uuid()

        super().save(*args, **kwargs)

    # pylint: disable=too-many-locals,too-many-branches
    @classmethod
    def query_data(cls, widget):
        """Queries and returns chart information with the data for the chart."""
        content_object = widget.content_object
        data_view = content_object if isinstance(content_object, DataView) else None
        if isinstance(content_object, XForm):
            xform = content_object
        elif data_view is not None:
            xform = data_view.xform
        else:
            raise Http404

        # Resolve every stored field before crossing the database boundary.
        # This also turns alternate field references into canonical XPaths.
        field, column = resolve_field_xpath(widget.column, xform)
        group_by_field = None
        group_by = None
        if widget.group_by:
            group_by_field, group_by = resolve_field_xpath(widget.group_by, xform)

        if data_view is not None:
            selected_columns = set(data_view.columns or [])
            if column not in selected_columns and column not in FIELD_DATA_MAP:
                raise Http404
            if group_by is not None and group_by not in selected_columns:
                raise Http404

        if isinstance(field, str):
            field_label, field_xpath, field_type = FIELD_DATA_MAP[field]
        else:
            field_label = get_field_label(field)
            field_xpath = column
            field_type = field.type if hasattr(field, "type") else ""
        data_type = DATA_TYPE_MAP.get(field_type, "categorized")

        if group_by and field_type in NUMERIC_LIST:
            records = get_form_submissions_aggregated_by_select_one(
                xform, column, column, group_by, data_view
            )
            # The legacy widget response exposes only sum and mean here.
            for record in records:
                record.pop("count", None)
        elif group_by and field_type == SELECT_ONE:
            records = get_form_submissions_grouped_by_select_one(
                xform, column, group_by, column, data_view
            )
        elif group_by:
            # This combination was never a valid widget query. Fail closed
            # rather than issuing malformed legacy SQL.
            raise Http404
        else:
            # The widget API exposes the complete _submission_time rather than
            # combining submissions into calendar-day buckets.
            records = get_form_submissions_grouped_by_field(
                xform,
                column,
                column,
                data_view,
                truncate_dates=column != SUBMISSION_TIME,
            )
            # The legacy query counted the extracted field rather than rows,
            # so the NULL bucket is present with a zero count.
            for record in records:
                if record.get(column) is None:
                    record["count"] = 0

        # flatten multiple dict if select one with group by
        if field_type == SELECT_ONE and group_by:
            records = _flatten_multiple_dict_into_one(column, group_by, records)
        # use labels if group by
        if group_by:
            choices = get_field_choices(group_by_field, xform)
            records = _use_labels_from_group_by_name(
                group_by, group_by_field, data_type, records, choices=choices
            )

        return {
            "field_type": field_type,
            "data_type": data_type,
            "field_xpath": field_xpath,
            "field_label": field_label,
            "grouped_by": group_by,
            "data": records,
        }
