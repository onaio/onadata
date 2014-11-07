from django.db import models
from django.contrib.auth.models import User

from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models import XForm


class ProjectXForm(models.Model):
    xform = models.ForeignKey(XForm, related_name='px_xforms')
    project = models.ForeignKey(Project, related_name='px_projects')
    created_by = models.ForeignKey(User, related_name='px_creator')

    class Meta:
        app_label = 'logger'
        unique_together = ('xform', 'project')
