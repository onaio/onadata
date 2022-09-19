# -*- coding: utf-8 -*-
"""
Module containing the XForm Version model
"""
from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class XFormVersion(models.Model):
    """
    XForm version model

    The main purpose of this model is to store the various
    versions of an XForm & link them to their respective xls files on the
    storage backend for utilization in the future when a user requires
    the previous XForm versions XML or JSON.
    """

    xform = models.ForeignKey(
        "logger.XForm", on_delete=models.CASCADE, related_name="versions"
    )
    xls = models.FileField()
    version = models.CharField(max_length=100)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    xml = models.TextField()
    json = models.TextField()

    def __str__(self):
        return f"{self.xform.title}-{self.version}"

    class Meta:
        unique_together = ["xform", "version"]
