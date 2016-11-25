from django.contrib.auth.models import User
from onadata.libs.permissions import ROLES
from onadata.libs.permissions import EditorRole, EditorMinorRole,\
    DataEntryRole, DataEntryMinorRole, DataEntryOnlyRole


class ShareXForm(object):
    def __init__(self, xform, username, role):
        self.xform = xform
        self.username = username
        self.role = role

    @property
    def user(self):
        return User.objects.get(username=self.username)

    def save(self, **kwargs):
        role = ROLES.get(self.role)

        # # check if there is xform meta perms set
        meta_perms = self.xform.metadata_set\
            .filter(data_type='xform_meta_perms')
        if meta_perms:
            meta_perm = meta_perms[0].data_value.split("|")

            if len(meta_perm) > 1:
                if role in [EditorRole, EditorMinorRole]:
                    role = ROLES.get(meta_perm[0])

                elif role in [DataEntryRole, DataEntryMinorRole,
                              DataEntryOnlyRole]:
                    role = ROLES.get(meta_perm[1])

        if role and self.user and self.xform:
            role.add(self.user, self.xform)
