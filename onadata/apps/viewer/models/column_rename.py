# -*- coding: utf-8 -*-
"""
ColumnRename model
"""
from django.db import models


class ColumnRename(models.Model):
    """
    ColumnRename model
    """

    xpath = models.CharField(max_length=255, unique=True)
    column_name = models.CharField(max_length=32)

    class Meta:
        app_label = "viewer"

    @classmethod
    def get_dict(cls):
        """Returns a dictionary where xpath is key and column_name is value"""
        return {cr.xpath: cr.column_name for cr in cls.objects.all()}
