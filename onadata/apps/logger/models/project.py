from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from guardian.shortcuts import assign_perm, get_perms_for_model
from jsonfield import JSONField
from taggit.managers import TaggableManager

from onadata.libs.models.base_model import BaseModel


class Project(BaseModel):
    class Meta:
        app_label = 'logger'
        unique_together = (('name', 'organization'),)
        permissions = (
            ('view_project', "Can view project"),
            ('add_project_xform', "Can add xform to project"),
            ("report_project_xform", "Can make submissions to the project"),
            ('transfer_project', "Can transfer project to different owner"),
            ('can_export_project_data', "Can export data in project"),
        )

    name = models.CharField(max_length=255)
    metadata = JSONField(blank=True)
    organization = models.ForeignKey(User, related_name='project_org')
    created_by = models.ForeignKey(User, related_name='project_owner')
    user_stars = models.ManyToManyField(User, related_name='project_stars')
    shared = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    tags = TaggableManager(related_name='project_tags')

    def __unicode__(self):
        return u'%s|%s' % (self.organization, self.name)

    def clean(self):
        query_set = Project.objects.exclude(pk=self.pk)\
            .filter(name__iexact=self.name, organization=self.organization)
        if query_set.exists():
            raise ValidationError(u'Project name "%s" is already in'
                                  u' use in this account.'
                                  % self.name.lower())


def set_object_permissions(sender, instance=None, created=False, **kwargs):
    if created:
        for perm in get_perms_for_model(Project):
            assign_perm(perm.codename, instance.organization, instance)

            if instance.created_by:
                assign_perm(perm.codename, instance.created_by, instance)


post_save.connect(set_object_permissions, sender=Project,
                  dispatch_uid='set_project_object_permissions')
