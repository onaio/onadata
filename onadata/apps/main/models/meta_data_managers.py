from django.contrib.contenttypes.models import ContentType
from django.db import models


class XFormMetaDataManager(models.Manager):
    def get_queryset(self):
        content_object, created = ContentType.objects.get_or_create(
            app_label="logger", model="xform")

        return super(XFormMetaDataManager, self).get_queryset().filter(
            content_type=content_object)


class ProjectMetaDataManager(models.Manager):
    def get_queryset(self):
        content_object, created = ContentType.objects.get_or_create(
            app_label="logger", model="project")

        return super(ProjectMetaDataManager, self).get_queryset().filter(
            content_type=content_object)
