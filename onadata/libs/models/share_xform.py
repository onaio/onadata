# -*- coding: utf-8 -*-
"""
ShareXForm model - facilitates sharing a form.
"""
from django.contrib.auth import get_user_model

from onadata.libs.permissions import (
    ROLES,
    DataEntryMinorRole,
    DataEntryOnlyRole,
    DataEntryRole,
    EditorMinorRole,
    EditorRole,
)


class ShareXForm:
    """ShareXForm class to facilitate sharing a form to a user with specified role."""

    def __init__(self, xform, username, role):
        self.xform = xform
        self.username = username
        self.role = role

    @property
    def user(self):
        """Returns the user object matching ``self.username``."""
        return get_user_model().objects.get(username=self.username)

    # pylint: disable=unused-argument
    def save(self, **kwargs):
        """Assign specified role permission to a user for the given form."""
        role = ROLES.get(self.role)

        # # check if there is xform meta perms set
        meta_perms = self.xform.metadata_set.filter(data_type="xform_meta_perms")
        if meta_perms:
            meta_perm = meta_perms[0].data_value.split("|")

            if len(meta_perm) > 1:
                if role in [EditorRole, EditorMinorRole]:
                    role = ROLES.get(meta_perm[0])

                elif role in [DataEntryRole, DataEntryMinorRole, DataEntryOnlyRole]:
                    role = ROLES.get(meta_perm[1])

        if role and self.user and self.xform:
            role.add(self.user, self.xform)
