# -*- coding: utf-8 -*-
"""
Survey type model class
"""
from django.db import models


class SurveyType(models.Model):
    """
    Survey type model class
    """

    slug = models.CharField(max_length=100, unique=True)

    class Meta:
        app_label = "logger"

    def __str__(self):
        return "SurveyType: %s" % self.slug
