from django.contrib.auth.models import User
from onadata.libs.permissions import ROLES, ManagerRole


class ShareProject(object):
    def __init__(self, project, username, role, remove=False):
        self.project = project
        self.username = username
        self.role = role
        self.remove = remove

    @property
    def user(self):
        return User.objects.get(username=self.username)

    def save(self, **kwargs):

        if self.remove:
            self.remove_user()
        else:
            role = ROLES.get(self.role)

            if role and self.user and self.project:
                role.add(self.user, self.project)

                # apply same role to forms under the project
                for xform in self.project.xform_set.all():
                    ManagerRole.add(self.user, xform)

    def remove_user(self):
        role = ROLES.get(self.role)

        if role and self.user and self.project:
            role._remove_obj_permissions(self.user, self.project)
