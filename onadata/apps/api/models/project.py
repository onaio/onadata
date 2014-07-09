from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from jsonfield import JSONField

from guardian.shortcuts import \
    assign_perm, \
    get_perms_for_model


class Project(models.Model):
    class Meta:
        app_label = 'api'
        unique_together = (('name', 'organization'),)
        permissions = (
            ('view_project', "Can view project"),
            ('add_xform', "Can add xform to project"),
            ('transfer_project', "Can transfer project to different owner"),
        )

    name = models.CharField(max_length=255)
    metadata = JSONField(default={}, null=True)
    organization = models.ForeignKey(User, related_name='project_organization')
    created_by = models.ForeignKey(User, related_name='project_creator')
    shared = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return u'%s|%s' % (self.organization, self.name)


def set_object_permissions(sender, instance=None, created=False, **kwargs):
    if created:
        for perm in get_perms_for_model(Project):
            assign_perm(perm.codename, instance.organization, instance)

            if instance.created_by:
                assign_perm(perm.codename, instance.created_by, instance)
post_save.connect(set_object_permissions, sender=Project,
                  dispatch_uid='set_project_object_permissions')
