from django.db import models
from django.contrib.auth.models import User, Group

from onadata.apps.api.models.project import Project


class Team(Group):
    """
    TODO: documentation
    TODO: Whenever a member is removed from members team,
          we  should remove them from all teams and projects
          within the organization.
    """
    class Meta:
        app_label = 'api'

    OWNER_TEAM_NAME = "Owners"

    organization = models.ForeignKey(User)
    projects = models.ManyToManyField(Project)

    def __unicode__(self):
        # return a clear group name without username to user for viewing
        return self.name.split('#')[1]

    @property
    def team_name(self):
        return self.__unicode__()

    def save(self, *args, **kwargs):
        # allow use of same name in different organizations/users
        # concat with #
        if not self.name.startswith('#'.join([self.organization.username])):
            self.name = u'%s#%s' % (self.organization.username, self.name)
        super(Team, self).save(*args, **kwargs)
