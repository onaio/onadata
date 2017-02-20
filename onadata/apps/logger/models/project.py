from django.db import models
from django.db.models import Prefetch
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from guardian.models import UserObjectPermissionBase
from guardian.models import GroupObjectPermissionBase
from guardian.shortcuts import assign_perm, get_perms_for_model
from taggit.managers import TaggableManager

from onadata.libs.models.base_model import BaseModel
from onadata.libs.utils.common_tags import OWNER_TEAM_NAME


class PrefetchManager(models.Manager):
    def get_queryset(self):
        from onadata.apps.logger.models.xform import XForm
        from onadata.apps.api.models.team import Team
        return super(PrefetchManager, self).get_queryset().select_related(
            'created_by', 'organization'
        ).prefetch_related(
            Prefetch('xform_set',
                     queryset=XForm.objects.filter(deleted_at__isnull=True)
                     .select_related('user')
                     .prefetch_related('user')
                     .prefetch_related('dataview_set')
                     .prefetch_related('metadata_set')
                     .only('id', 'user', 'project', 'title', 'date_created',
                           'last_submission_time', 'num_of_submissions',
                           'downloadable'),
                     to_attr='xforms_prefetch')
        ).prefetch_related('tags')\
            .prefetch_related(Prefetch(
                'projectuserobjectpermission_set',
                queryset=ProjectUserObjectPermission.objects.select_related(
                    'user__profile__organizationprofile',
                    'permission'
                )
            ))\
            .prefetch_related(Prefetch(
                'projectgroupobjectpermission_set',
                queryset=ProjectGroupObjectPermission.objects.select_related(
                    'group',
                    'permission'
                )
            )).prefetch_related('user_stars')\
            .prefetch_related(Prefetch(
                'organization__team_set',
                queryset=Team.objects.all().prefetch_related('user_set')
            ))


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
            ("view_project_all", "Can view all associated data"),
            ("view_project_data", "Can view submitted data"),
        )

    name = models.CharField(max_length=255)
    metadata = JSONField(default=dict)
    organization = models.ForeignKey(User, related_name='project_org')
    created_by = models.ForeignKey(User, related_name='project_owner')
    user_stars = models.ManyToManyField(User, related_name='project_stars')
    shared = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    tags = TaggableManager(related_name='project_tags')
    prefetched = PrefetchManager()

    def __unicode__(self):
        return u'%s|%s' % (self.organization, self.name)

    def clean(self):
        query_set = Project.objects.exclude(pk=self.pk)\
            .filter(name__iexact=self.name, organization=self.organization)
        if query_set.exists():
            raise ValidationError(u'Project name "%s" is already in'
                                  u' use in this account.'
                                  % self.name.lower())

    @property
    def user(self):
        return self.created_by


def set_object_permissions(sender, instance=None, created=False, **kwargs):
    if created:
        for perm in get_perms_for_model(Project):
            assign_perm(perm.codename, instance.organization, instance)

            owners = instance.organization.team_set\
                .filter(name="{}#{}".format(instance.organization.username,
                        OWNER_TEAM_NAME), organization=instance.organization)
            for owner in owners:
                assign_perm(perm.codename, owner, instance)

            if instance.created_by:
                assign_perm(perm.codename, instance.created_by, instance)


post_save.connect(set_object_permissions, sender=Project,
                  dispatch_uid='set_project_object_permissions')


class ProjectUserObjectPermission(UserObjectPermissionBase):
    """Guardian model to create direct foreign keys."""

    content_object = models.ForeignKey(Project)


class ProjectGroupObjectPermission(GroupObjectPermissionBase):
    """Guardian model to create direct foreign keys."""

    content_object = models.ForeignKey(Project)
