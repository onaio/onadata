from future.utils import python_2_unicode_compatible

from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User, Group
from guardian.shortcuts import assign_perm, get_perms_for_model

from onadata.apps.logger.models.project import Project


@python_2_unicode_compatible
class Team(Group):
    """
    TODO: documentation
    TODO: Whenever a member is removed from members team,
    we  should remove them from all teams and projects
    within the organization.
    """
    class Meta:
        app_label = 'api'
        permissions = (
            ('view_team', "Can view team."),
        )

    OWNER_TEAM_NAME = "Owners"

    organization = models.ForeignKey(User)
    projects = models.ManyToManyField(Project)
    created_by = models.ForeignKey(User, related_name='team_creator',
                                   null=True, blank=True)

    date_created = models.DateTimeField(auto_now_add=True, null=True,
                                        blank=True)
    date_modified = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        # return a clear group name without username to user for viewing
        return self.name.split('#')[1]

    @property
    def team_name(self):
        return self.__str__()

    def save(self, *args, **kwargs):
        # allow use of same name in different organizations/users
        # concat with #
        if not self.name.startswith('#'.join([self.organization.username])):
            self.name = u'%s#%s' % (self.organization.username, self.name)
        super(Team, self).save(*args, **kwargs)


def set_object_permissions(sender, instance=None, created=False, **kwargs):
    if created:
        for perm in get_perms_for_model(Team):
            assign_perm(perm.codename, instance.organization, instance)
            organization = instance.organization.profile

            if instance.created_by:
                assign_perm(perm.codename, instance.created_by, instance)
            if hasattr(organization, 'creator') and \
                    organization.creator != instance.created_by:
                assign_perm(perm.codename, organization.creator, instance)
            if organization.created_by != instance.created_by:
                assign_perm(perm.codename, organization.created_by, instance)


post_save.connect(set_object_permissions, sender=Team,
                  dispatch_uid='set_team_object_permissions')
