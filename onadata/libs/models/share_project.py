# -*- coding: utf-8 -*-
"""
ShareProject model - facilitate sharing of a project to a user.
"""
from django.contrib.auth import get_user_model
from django.db import transaction

from onadata.libs.permissions import (
    ROLES,
    DataEntryMinorRole,
    DataEntryOnlyRole,
    DataEntryRole,
    EditorMinorRole,
    EditorRole,
)
from onadata.libs.utils.cache_tools import (
    PROJ_OWNER_CACHE,
    PROJ_PERM_CACHE,
    safe_delete,
)
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.project_utils import propagate_project_permissions_async


# pylint: disable=invalid-name
User = get_user_model()


def remove_xform_permissions(project, user, role):
    """Remove user permissions to all forms for the given ``project``."""
    # remove role from project forms as well
    xform_qs = project.xform_set.all()
    for xform in queryset_iterator(xform_qs):
        # pylint: disable=protected-access
        role._remove_obj_permissions(user, xform)
        # Removed MergedXForm permissions if XForm is also a MergedXForm
        if hasattr(xform, "mergedxform"):
            role._remove_obj_permissions(user, xform.mergedxform)


def remove_dataview_permissions(project, user, role):
    """Remove user permissions to all dataviews for the given ``project``."""
    dataview_qs = project.dataview_set.all()
    for dataview in queryset_iterator(dataview_qs):
        # pylint: disable=protected-access
        role._remove_obj_permissions(user, dataview.xform)


def remove_entity_list_permissions(project, user, role):
    """Remove user permissions for all entitylists for the given project"""
    entity_list_qs = project.entity_lists.all()
    for entity_list in queryset_iterator(entity_list_qs):
        # pylint: disable=protected-access
        role._remove_obj_permissions(user, entity_list)


class ShareProject:
    """Share project with a user."""

    def __init__(self, project, username, role, remove=False):
        self.project = project
        self.username = username
        self.role = role
        self.remove = remove

    @property
    def user(self):
        """Return the user object for the given ``self.username``."""
        return User.objects.get(username=self.username)

    # pylint: disable=unused-argument
    @transaction.atomic()
    def save(self, **kwargs):
        """Assigns role permissions to a project for the user."""
        # pylint: disable=too-many-nested-blocks
        if self.remove:
            self.__remove_user()
        else:
            role = ROLES.get(self.role)

            if role and self.user and self.project:
                role.add(self.user, self.project)

                # apply same role to forms under the project
                xform_qs = self.project.xform_set.all()
                for xform in queryset_iterator(xform_qs):
                    # check if there is xform meta perms set
                    meta_perms = xform.metadata_set.filter(data_type="xform_meta_perms")
                    if meta_perms:
                        meta_perm = meta_perms[0].data_value.split("|")

                        if len(meta_perm) > 1:
                            if role in [EditorRole, EditorMinorRole]:
                                role = ROLES.get(meta_perm[0])

                            elif role in [
                                DataEntryRole,
                                DataEntryMinorRole,
                                DataEntryOnlyRole,
                            ]:
                                role = ROLES.get(meta_perm[1])
                    role.add(self.user, xform)

                    # Set MergedXForm permissions if XForm is also a MergedXForm
                    if hasattr(xform, "mergedxform"):
                        role.add(self.user, xform.mergedxform)

                dataview_qs = self.project.dataview_set.all()
                for dataview in queryset_iterator(dataview_qs):
                    if dataview.matches_parent:
                        role.add(self.user, dataview.xform)

                # Apply same role to EntityLists under project
                entity_list_qs = self.project.entity_lists.all()
                for entity_list in queryset_iterator(entity_list_qs):
                    role.add(self.user, entity_list)

        # clear cache
        safe_delete(f"{PROJ_OWNER_CACHE}{self.project.pk}")
        safe_delete(f"{PROJ_PERM_CACHE}{self.project.pk}")
        # propagate KPI permissions
        propagate_project_permissions_async.apply_async(args=[self.project.pk])

    @transaction.atomic()
    def __remove_user(self):
        role = ROLES.get(self.role)

        if role and self.user and self.project:
            remove_xform_permissions(self.project, self.user, role)
            remove_dataview_permissions(self.project, self.user, role)
            remove_entity_list_permissions(self.project, self.user, role)
            # pylint: disable=protected-access
            role._remove_obj_permissions(self.user, self.project)
