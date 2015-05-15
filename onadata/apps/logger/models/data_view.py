from django.contrib.gis.db import models
from jsonfield import JSONField

from onadata.libs.models.base_model import BaseModel


class DataView(BaseModel):
    """
    Model to provide filtered access to the underlying data of an XForm
    """
    class Meta:
        app_label = 'logger'

    name = models.CharField(max_length=255)
    xform = models.ForeignKey('XForm')
    project = models.ForeignKey('Project')

    columns = JSONField()
    query = JSONField()