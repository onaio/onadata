from django.db import models
from django.contrib.auth.models import User

from onadata.apps.api.models.project import Project
from onadata.apps.logger.models import XForm


class ProjectXForm(models.Model):
    xform = models.ForeignKey(XForm)
    project = models.ForeignKey(Project)
    created_by = models.ForeignKey(User)

    class Meta:
        app_label = 'api'
        unique_together = ('xform', 'project')
