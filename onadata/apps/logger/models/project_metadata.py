import os
from django.db import models

from onadata.apps.logger.models import Project


def upload_to(instance, filename):
    return os.path.join(instance.project.name, 'docs', filename)


class ProjectDocuments(models.Model):
    project = models.ForeignKey(Project)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)
    document_value = models.CharField(max_length=255)
    document_file = models.FileField(
        upload_to=upload_to, blank=True, null=True)
    document_file_type = models.CharField(
        max_length=255, blank=True, null=True)
    file_hash = models.CharField(max_length=50, blank=True, null=True)
    date_created = models.DateTimeField(null=True, auto_now_add=True)
    date_modified = models.DateTimeField(null=True, auto_now=True)
    deleted_at = models.DateTimeField(null=True, default=None)

    class Meta:
        app_label = 'logger'
