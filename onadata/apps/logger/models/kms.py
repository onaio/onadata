"""
Key management models
"""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models.xform import XForm
from onadata.libs.models import BaseModel


class KMSKey(BaseModel):
    class KMSProvider(models.IntegerChoices):
        AWS = 1, _("AWS")

    key_id = models.CharField(max_length=255)
    description = models.CharField(null=True, blank=True, max_length=255)
    public_key = models.TextField()
    provider = models.IntegerField(choices=KMSProvider.choices)
    next_rotation_at = models.DateTimeField(null=True, blank=True)
    last_rotation_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta(BaseModel.Meta):
        app_label = "logger"
        unique_together = ("key_id", "provider")

    def __str__(self):
        return self.key_id


class XFormKey(BaseModel):
    xform = models.ForeignKey(XForm, on_delete=models.CASCADE, related_name="kms_keys")
    kms_key = models.ForeignKey(KMSKey, on_delete=models.CASCADE, related_name="xforms")

    class Meta(BaseModel.Meta):
        app_label = "logger"
        unique_together = ("xform", "kms_key")
