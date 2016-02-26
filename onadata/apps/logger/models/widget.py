from django.contrib.gis.db import models
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from ordered_model.models import OrderedModel
from querybuilder.query import Query
from querybuilder.fields import CountField

from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.data_view import DataView
from onadata.libs.utils.model_tools import generate_uuid_for_form
from onadata.libs.utils.chart_tools import get_field_from_field_name,\
    DATA_TYPE_MAP, get_field_label
from onadata.libs.utils.common_tags import SUBMISSION_TIME


class Widget(OrderedModel):
    CHARTS = 'charts'

    # Other widgets types to be added later
    WIDGETS_TYPES = (
        (CHARTS, 'Charts'),
    )

    # Will hold either XForm or DataView Model
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    widget_type = models.CharField(max_length=25, choices=WIDGETS_TYPES,
                                   default=CHARTS)
    view_type = models.CharField(max_length=50)
    column = models.CharField(max_length=50)
    group_by = models.CharField(null=True, default=None, max_length=50,
                                blank=True)

    title = models.CharField(null=True, default=None, max_length=50,
                             blank=True)
    description = models.CharField(null=True, default=None, max_length=255,
                                   blank=True)
    aggregation = models.CharField(null=True, default=None, max_length=255,
                                   blank=True)
    key = models.CharField(db_index=True, unique=True, max_length=32)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    order_with_respect_to = 'content_type'

    class Meta(OrderedModel.Meta):
        app_label = 'logger'

    def save(self, *args, **kwargs):

        if not self.key:
            self.key = generate_uuid_for_form()

        super(Widget, self).save(*args, **kwargs)

    @classmethod
    def query_data(cls, widget):

        # get the columns needed
        column = widget.column
        group_by = widget.group_by

        if isinstance(widget.content_object, XForm):
            xform = widget.content_object
        elif isinstance(widget.content_object, DataView):
            xform = widget.content_object.xform

        columns = [{column: "json->>'%s'" % unicode(column)},
                   CountField(field="json->>'%s'" % unicode(column),
                              alias="count")]
        if group_by:
            columns += [{group_by: "json->>'%s'" % unicode(group_by)}]

        query = Query().from_table(Instance, columns).where(xform_id=xform.pk,
                                                            deleted_at=None)
        query.group_by("json->>'%s'" % unicode(column))
        if group_by:
            query.group_by("json->>'%s'" % unicode(group_by))

        records = query.select()

        field = get_field_from_field_name(column, xform.data_dictionary())
        if isinstance(field, basestring) and field == SUBMISSION_TIME:
            field_label = 'Submission Time'
            field_xpath = '_submission_time'
            field_type = 'datetime'
            data_type = DATA_TYPE_MAP.get(field_type, 'categorized')
        else:
            field_type = field.type
            data_type = DATA_TYPE_MAP.get(field.type, 'categorized')
            field_xpath = field.get_abbreviated_xpath()
            field_label = get_field_label(field)

        return {
            "field_type": field_type,
            "data_type": data_type,
            "field_xpath": field_xpath,
            "field_label": field_label,
            "group_by": group_by,
            "data": records
        }
