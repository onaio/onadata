# -*- coding: utf-8 -*-
"""
ShareXForm model - facilitates sharing a form.
"""

from django.contrib.auth import get_user_model

from onadata.apps.api.tools import update_role_by_meta_xform_perms
from onadata.libs.permissions import (
    ROLES,
)
from onadata.libs.utils.common_tags import XFORM_META_PERMS


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

        meta_perms = self.xform.metadata_set.filter(data_type=XFORM_META_PERMS)
        if meta_perms:
            update_role_by_meta_xform_perms(self.xform, user=self.user, user_role=role)
        elif role and self.user and self.xform:
            role.add(self.user, self.xform)
