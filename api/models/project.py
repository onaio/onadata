from django.db import models
from django.contrib.auth.models import User


class Project(models.Model):
    class Meta:
        app_label = 'api'
        unique_together = (('name', 'organization'),)

    name = models.CharField(max_length=255)
    organization = models.ForeignKey(User, related_name='project_organization')
    created_by = models.ForeignKey(User, related_name='project_creator')

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return u'%s|%s' % (self.organization, self.name)
