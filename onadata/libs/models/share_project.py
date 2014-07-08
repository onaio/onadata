from django.contrib.auth.models import User
from onadata.libs.permissions import ROLES


class ShareProject(object):
    def __init__(self, project, username, role):
        self.project = project
        self.username = username
        self.role = role

    @property
    def user(self):
        return User.objects.get(username=self.username)

    def save(self, **kwargs):
        role = ROLES.get(self.role)

        if role and self.user and self.project:
            role.add(self.user, self.project)
