# -*- coding: utf-8 -*-
"""
BaseModel abstract class - sets date_created/date_modified fields.
"""

from django.db import models


class BaseModel(models.Model):
    """
    BaseModel abstract class - sets date_created/date_modified fields.
    """

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    """Custom queryset that only returns objects that have not been deleted"""

    def active(self):
        """Return only objects that have not been deleted"""
        return self.filter(deleted_at__isnull=True)

    def all_with_deleted(self):
        """Return all objects, including those that have been deleted"""
        return self


class SoftDeleteManager(models.Manager):
    """Custom manager that only returns objects that have not been deleted"""

    def get_queryset(self):
        """Return queryset that only returns objects that have not been deleted"""
        return SoftDeleteQuerySet(self.model, using=self._db).active()

    def all_with_deleted(self):
        """Return all objects, including those that have been deleted"""
        return SoftDeleteQuerySet(self.model, using=self._db)
