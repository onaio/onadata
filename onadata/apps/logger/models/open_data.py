from django.contrib.gis.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from onadata.libs.utils.common_tools import getUUID


class OpenData(models.Model):
    name = models.CharField(max_length=255)
    uuid = models.CharField(max_length=32, default=getUUID, unique=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    active = models.BooleanField(default=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return getattr(self, "name", "")

    class Meta:
        app_label = 'logger'
