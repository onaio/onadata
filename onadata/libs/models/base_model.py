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
