"""AbstractBase model"""

from django.db import models


class AbstractBase(models.Model):
    """Common information for models"""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
