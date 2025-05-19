# -*- coding: utf-8 -*-
"""
ShareTeamProject model - facilitate sharing a project to a team.
"""

from onadata.libs.permissions import (
    ROLES,
)
from onadata.libs.utils.cache_tools import PROJ_PERM_CACHE, safe_delete
from onadata.libs.utils.xform_utils import update_role_by_meta_xform_perms
from onadata.libs.utils.common_tags import XFORM_META_PERMS


class ShareTeamProject:
    """Share a project to a team for the given role."""

    def __init__(self, team, project, role, remove=False):
        self.team = team
        self.project = project
        self.role = role
        self.remove = remove

    # pylint: disable=unused-argument
    def save(self, **kwargs):
        """Assigns project role permissions to the team."""
        # pylint: disable=too-many-nested-blocks
        if self.remove:
            self.remove_team()
        else:
            role = ROLES.get(self.role)

            if role and self.team and self.project:
                role.add(self.team, self.project)

                for xform in self.project.xform_set.all():
                    role.add(self.team, xform)

                    if xform.metadata_set.filter(data_type=XFORM_META_PERMS):
                        update_role_by_meta_xform_perms(xform)

                for dataview in self.project.dataview_set.all():
                    if dataview.matches_parent:
                        role.add(self.team, dataview.xform)

            # clear cache
            safe_delete(f"{PROJ_PERM_CACHE}{self.project.pk}")

    def remove_team(self):
        """Removes team permissions from a project."""
        role = ROLES.get(self.role)

        if role and self.team and self.project:
            # pylint: disable=protected-access
            role._remove_obj_permissions(self.team, self.project)

            for xform in self.project.xform_set.all():
                # pylint: disable=protected-access
                role._remove_obj_permissions(self.team, xform)

            for dataview in self.project.dataview_set.all():
                # pylint: disable=protected-access
                role._remove_obj_permissions(self.team, dataview.xform)
