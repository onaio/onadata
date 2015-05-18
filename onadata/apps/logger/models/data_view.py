from django.contrib.gis.db import models

from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.project import Project
from jsonfield import JSONField


class DataView(models.Model):
    """
    Model to provide filtered access to the underlying data of an XForm
    """
    name = models.CharField(max_length=255)
    xform = models.ForeignKey(XForm)
    project = models.ForeignKey(Project)

    columns = JSONField()
    query = JSONField()

    class Meta:
        app_label = 'logger'
