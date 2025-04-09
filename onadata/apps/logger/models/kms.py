"""Key management models"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models.xform import XForm
from onadata.libs.models import BaseModel

User = get_user_model()


class KMSKey(BaseModel):
    """Managed encryption keys."""

    # pylint: disable=too-many-ancestors
    class KMSProvider(models.IntegerChoices):
        """Managed keys service providers"""

        AWS = 1, _("AWS")

    key_id = models.CharField(max_length=255)
    description = models.CharField(null=True, blank=True, max_length=255)
    public_key = models.TextField()
    provider = models.IntegerField(choices=KMSProvider.choices)
    expiry_date = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    disabled_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta(BaseModel.Meta):
        app_label = "logger"
        unique_together = ("key_id", "provider")
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["disabled_at"]),
        ]

    def __str__(self):
        return self.key_id

    @property
    def is_expired(self):
        """Returns True if key is expired, False otherwise."""
        return timezone.now() > self.expiry_date


class XFormKey(BaseModel):
    """Forms encrypted using managed keys."""

    xform = models.ForeignKey(XForm, on_delete=models.CASCADE, related_name="kms_keys")
    kms_key = models.ForeignKey(KMSKey, on_delete=models.CASCADE, related_name="xforms")
    version = models.CharField(max_length=255, help_text=_("XForm version"))
    encrypted_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    class Meta(BaseModel.Meta):
        app_label = "logger"
        unique_together = ("xform", "kms_key", "version")
        indexes = [models.Index(fields=["xform", "version"])]
