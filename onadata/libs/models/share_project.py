from django.contrib.auth.models import User

from onadata.libs.permissions import ROLES
from onadata.libs.utils.cache_tools import PROJ_PERM_CACHE, safe_delete


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
                    role.add(self.user, xform)
        # clear cache
        safe_delete('{}{}'.format(PROJ_PERM_CACHE, self.project.pk))

    def remove_user(self):
        role = ROLES.get(self.role)

        if role and self.user and self.project:
            role._remove_obj_permissions(self.user, self.project)

            # remove role from project forms as well
            for xform in self.project.xform_set.all():
                role._remove_obj_permissions(self.user, xform)
