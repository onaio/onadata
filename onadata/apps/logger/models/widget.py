from enumfields import EnumField
from enum import Enum

from django.contrib.gis.db import models
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Widget(models.Model):

    class WidgetType(Enum):
        """
        Will be expanded to include table and map widget types
        """
        CHART = 'chart'

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    widget_type = EnumField(WidgetType, max_length=1)
    view_type = models.CharField()
    column = models.CharField()
    group_by = models.CharField(null=True, default=None)
    title = models.CharField(null=True, default=None)
    description = models.CharField(null=True, default=None)
    key = models.CharField()
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

