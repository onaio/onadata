from django.contrib.auth.models import User
from django.db import transaction

from onadata.libs.permissions import ROLES
from onadata.libs.permissions import EditorRole, EditorMinorRole,\
    DataEntryRole, DataEntryMinorRole, DataEntryOnlyRole
from onadata.libs.utils.cache_tools import PROJ_PERM_CACHE, safe_delete


def remove_xform_permissions(project, user, role):
    # remove role from project forms as well
    for xform in project.xform_set.all():
        role._remove_obj_permissions(user, xform)


def remove_dataview_permissions(project, user, role):
    for dataview in project.dataview_set.all():
        role._remove_obj_permissions(user, dataview.xform)


class ShareProject(object):

    def __init__(self, project, username, role, remove=False):
        self.project = project
        self.username = username
        self.role = role
        self.remove = remove

    @property
    def user(self):
        return User.objects.get(username=self.username)

    @transaction.atomic()
    def save(self, **kwargs):

        if self.remove:
            self.__remove_user()
        else:
            role = ROLES.get(self.role)

            if role and self.user and self.project:
                role.add(self.user, self.project)

                # apply same role to forms under the project
                for xform in self.project.xform_set.all():
                    # check if there is xform meta perms set
                    meta_perms = xform.metadata_set \
                        .filter(data_type='xform_meta_perms')
                    if meta_perms:
                        meta_perm = meta_perms[0].data_value.split("|")

                        if len(meta_perm) > 1:
                            if role in [EditorRole, EditorMinorRole]:
                                role = ROLES.get(meta_perm[0])

                            elif role in [DataEntryRole, DataEntryMinorRole,
                                          DataEntryOnlyRole]:
                                role = ROLES.get(meta_perm[1])
                    role.add(self.user, xform)

                for dataview in self.project.dataview_set.all():
                    if dataview.matches_parent:
                        role.add(self.user, dataview.xform)

        # clear cache
        safe_delete('{}{}'.format(PROJ_PERM_CACHE, self.project.pk))

    @transaction.atomic()
    def __remove_user(self):
        role = ROLES.get(self.role)

        if role and self.user and self.project:
            remove_xform_permissions(self.project, self.user, role)
            remove_dataview_permissions(self.project, self.user, role)
            role._remove_obj_permissions(self.user, self.project)
