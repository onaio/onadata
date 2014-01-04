from django.db import models
from django.contrib.auth.models import User

from api.models.project import Project
from odk_logger.models import XForm


class ProjectXForm(models.Model):
    xform = models.ForeignKey(XForm)
    project = models.ForeignKey(Project)
    created_by = models.ForeignKey(User)

    class Meta:
        app_label = 'api'
        unique_together = ('xform', 'project')
