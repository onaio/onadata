from django.contrib.gis.db import models
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

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
