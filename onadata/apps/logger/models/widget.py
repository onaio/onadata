# -*- coding: utf-8 -*-
"""
Widget class module.
"""

from builtins import str as text

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from django.db.models import JSONField

from ordered_model.models import OrderedModel
from pyxform.question import Option
from querybuilder.fields import AvgField, CountField, SimpleField, SumField
from querybuilder.query import Query

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.chart_tools import (
    DATA_TYPE_MAP,
    _flatten_multiple_dict_into_one,
    _use_labels_from_group_by_name,
    get_field_choices,
    get_field_from_field_xpath,
    get_field_label,
)
from onadata.libs.utils.common_tags import NUMERIC_LIST, SELECT_ONE, SUBMISSION_TIME
from onadata.libs.utils.common_tools import get_abbreviated_xpath, get_uuid


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
        # get the columns needed
        column = widget.column
        group_by = widget.group_by if widget.group_by else None
        xform = None

        if isinstance(widget.content_object, XForm):
            xform = widget.content_object
        elif isinstance(widget.content_object, DataView):
            xform = widget.content_object.xform

        field = get_field_from_field_xpath(column, xform)

        if isinstance(field, str) and field == SUBMISSION_TIME:
            field_label = "Submission Time"
            field_xpath = "_submission_time"
            field_type = "datetime"
            data_type = DATA_TYPE_MAP.get(field_type, "categorized")
        else:
            field_type = field.type if hasattr(field, "type") else ""
            data_type = DATA_TYPE_MAP.get(field_type, "categorized")
            field_xpath = get_abbreviated_xpath(field.get_xpath())
            if isinstance(field, Option):
                parent = get_field_from_field_xpath(
                    "/".join(column.split("/")[:-1]), xform
                )
                field_xpath = get_abbreviated_xpath(
                    parent.get_xpath() + field.get_xpath()
                )
            field_label = get_field_label(field)

        columns = [
            SimpleField(field=f"json->>'{text(column)}'", alias=f"{column}"),
            CountField(field=f"json->>'{text(column)}'", alias="count"),
        ]

        if group_by:
            if field_type in NUMERIC_LIST:
                column_field = SimpleField(
                    field=f"json->>'{text(column)}'", cast="float", alias=column
                )
            else:
                column_field = SimpleField(
                    field=f"json->>'{text(column)}'", alias=column
                )

            # build inner query
            inner_query_columns = [
                column_field,
                SimpleField(field=f"json->>'{text(group_by)}'", alias=group_by),
                SimpleField(field="xform_id"),
                SimpleField(field="deleted_at"),
            ]
            inner_query = Query().from_table(Instance, inner_query_columns)

            # build group-by query
            if field_type in NUMERIC_LIST:
                columns = [
                    SimpleField(field=group_by, alias=f"{group_by}"),
                    SumField(field=column, alias="sum"),
                    AvgField(field=column, alias="mean"),
                ]
            elif field_type == SELECT_ONE:
                columns = [
                    SimpleField(field=column, alias=f"{column}"),
                    SimpleField(field=group_by, alias=f"{group_by}"),
                    CountField(field="*", alias="count"),
                ]

            query = (
                Query()
                .from_table({"inner_query": inner_query}, columns)
                .where(xform_id=xform.pk, deleted_at=None)
            )

            if field_type == SELECT_ONE:
                query.group_by(column).group_by(group_by)
            else:
                query.group_by(group_by)

        else:
            query = (
                Query()
                .from_table(Instance, columns)
                .where(xform_id=xform.pk, deleted_at=None)
            )
            query.group_by(f"json->>'{text(column)}'")

        # run query
        records = query.select()

        # flatten multiple dict if select one with group by
        if field_type == SELECT_ONE and group_by:
            records = _flatten_multiple_dict_into_one(column, group_by, records)
        # use labels if group by
        if group_by:
            group_by_field = get_field_from_field_xpath(group_by, xform)
            choices = get_field_choices(group_by, xform)
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
