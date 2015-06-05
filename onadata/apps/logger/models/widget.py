from django.utils.translation import ugettext as _
from querybuilder.query import Query
from querybuilder.fields import CountField
from django.contrib.gis.db import models
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.data_view import DataView
from onadata.libs.utils.model_tools import generate_uuid_for_form


class Widget(models.Model):
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
    key = models.CharField(db_index=True, unique=True, max_length=32)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'logger'

    def save(self, *args, **kwargs):

        self.key = generate_uuid_for_form()

        super(Widget, self).save(*args, **kwargs)

    @classmethod
    def query_chart(cls, widget):

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

        return records
