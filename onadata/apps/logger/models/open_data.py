# -*- coding: utf-8 -*-
"""
OpenData model represents a way to access private datasets without
authentication using the unique uuid.
"""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from django.utils.encoding import python_2_unicode_compatible

from onadata.libs.utils.common_tools import get_uuid


@python_2_unicode_compatible
class OpenData(models.Model):
    """
    OpenData model represents a way to access private datasets without
    authentication using the unique uuid.
    """
    name = models.CharField(max_length=255)
    uuid = models.CharField(max_length=32, default=get_uuid, unique=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    active = models.BooleanField(default=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return getattr(self, "name", "")

    class Meta:
        app_label = 'logger'


def get_or_create_opendata(xform):
    """
    Looks up an OpenData object with the given xform, creates one if it does
    not exist.
    Returns a tuple of (object, created), where created is a boolean specifing
    whether an object was created.
    """
    content_type = ContentType.objects.get_for_model(xform)

    return OpenData.objects.get_or_create(
        object_id=xform.id,
        defaults={
            'name': xform.id_string,
            'content_type': content_type,
            'content_object': xform,
        }
    )
