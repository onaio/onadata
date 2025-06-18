# -*- coding: utf-8 -*-
"""
project_utils module - apply project permissions to a form.
"""

import sys

from django.conf import settings
from django.db import IntegrityError
from django.apps import apps
from guardian.shortcuts import get_perms

from multidb.pinning import use_master

from onadata.celeryapp import app
from onadata.libs.utils.cache_tools import (
    XFORM_DATA_VERSIONS,
    XFORM_METADATA_CACHE,
    XFORM_PERMISSIONS_CACHE,
    PROJ_OWNER_CACHE,
    safe_delete,
)
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.permissions import (
    ROLES,
    ReadOnlyRole,
    get_object_users_with_permissions,
    set_project_perms_to_object,
    get_role,
    is_organization,
    DataEntryMinorRole,
    DataEntryOnlyRole,
    DataEntryRole,
    EditorNoDownload,
    EditorMinorRole,
    EditorRole,
    ReadOnlyRoleNoDownload,
)
from onadata.libs.utils.common_tools import report_exception
from onadata.libs.utils.common_tags import MEMBERS
from onadata.libs.utils.project_utils import get_project_users


def get_team_members(org_username):
    """Return members team if it exists else none.

    :param org_username: organization name
    :return: team
    """
    members = []
    # pylint: disable=invalid-name
    Team = apps.get_model("api", "Team")  # noqa: N806

    try:
        team = Team.objects.get(name=f"{org_username}#{MEMBERS}")
    except Team.DoesNotExist:
        pass
    else:
        members = team.user_set.all()

    return members


def set_project_perms_to_xform(xform, project):
    """
    Apply project permissions to a form, this usually happens when a new form
    is being published or it is being moved to a new project.
    """
    # allows us to still use xform.shared and xform.shared_data as before
    # only switch if xform.shared is False
    xform_is_shared = xform.shared or xform.shared_data
    if not xform_is_shared and project.shared != xform.shared:
        xform.shared = project.shared
        xform.shared_data = project.shared
        xform.save()

    # clear existing permissions
    for perm in get_object_users_with_permissions(xform, with_group_users=True):
        user = perm["user"]
        role_name = perm["role"]
        role = ROLES.get(role_name)
        if role and (user not in (xform.user, project.user, project.created_by)):
            role.remove_obj_permissions(user, xform)

    set_project_perms_to_object(xform, project)


def get_xform_users(xform):
    """
    Utility function that returns users and their roles in a form.
    :param xform:
    :return:
    """
    data = {}
    org_members = []
    xform_user_obj_perm_qs = xform.xformuserobjectpermission_set.all()
    # pylint: disable=invalid-name
    UserProfile = apps.get_model("main", "UserProfile")  # noqa: N806

    for perm in queryset_iterator(xform_user_obj_perm_qs):
        if perm.user not in data:
            user = perm.user

            # create default profile if missing
            try:
                profile = user.profile
            except UserProfile.DoesNotExist:
                profile = UserProfile.objects.create(user=user)

            if is_organization(user.profile):
                org_members = get_team_members(user.username)

            data[user] = {
                "permissions": [],
                "is_org": is_organization(profile),
                "metadata": profile.metadata,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user": user.username,
            }
        if perm.user in data:
            data[perm.user]["permissions"].append(perm.permission.codename)

    for user in org_members:
        # create default profile if missing
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=user)

        if user not in data:
            data[user] = {
                "permissions": get_perms(user, xform),
                "is_org": is_organization(profile),
                "metadata": profile.metadata,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user": user.username,
            }

    for value in data.values():
        value["permissions"].sort()
        value["role"] = get_role(value["permissions"], xform)
        del value["permissions"]

    return data


def clear_permissions_cache(xform):
    safe_delete(f"{PROJ_OWNER_CACHE}{xform.project.pk}")
    safe_delete(f"{XFORM_METADATA_CACHE}{xform.pk}")
    safe_delete(f"{XFORM_DATA_VERSIONS}{xform.pk}")
    safe_delete(f"{XFORM_PERMISSIONS_CACHE}{xform.pk}")


def update_role_by_meta_xform_perms(xform, user=None, user_role=None):
    """
    Updates users role in a xform based on meta permissions set on the form.
    """

    clear_permissions_cache(xform)

    # pylint: disable=invalid-name
    MetaData = apps.get_model("main", "MetaData")  # noqa: N806
    metadata = MetaData.xform_meta_permission(xform)
    editor_role_list = [EditorNoDownload, EditorRole, EditorMinorRole]
    editor_role = {role.name: role for role in editor_role_list}

    dataentry_role_list = [DataEntryMinorRole, DataEntryOnlyRole, DataEntryRole]
    dataentry_role = {role.name: role for role in dataentry_role_list}

    readonly_role_list = [ReadOnlyRole, ReadOnlyRoleNoDownload]
    readonly_role = {role.name: role for role in readonly_role_list}

    project_users = get_project_users(xform.project)

    if metadata:
        meta_perms = metadata.data_value.split("|")

        if user:
            users = [user]
        else:
            users = get_xform_users(xform)

        # update roles
        for xform_user in users:
            if user_role:
                role = user_role.name
            else:
                role = users.get(xform_user).get("role")

            if role in editor_role:
                role = ROLES.get(meta_perms[0])
                role.add(xform_user, xform)

            if role in dataentry_role:
                role = ROLES.get(meta_perms[1])
                role.add(xform_user, xform)

            if role in readonly_role:
                project_user_role = project_users[xform_user.username]["role"]
                if project_user_role == ReadOnlyRole.name:
                    role = ROLES.get(meta_perms[2])
                    role.add(xform_user, xform)


# pylint: disable=invalid-name
@app.task(bind=True, max_retries=3)
def set_project_perms_to_xform_async(self, xform_id, project_id):
    """
    Apply project permissions for ``project_id`` to a form ``xform_id`` task.
    """
    # pylint: disable=invalid-name
    XForm = apps.get_model("logger", "XForm")  # noqa: N806
    # pylint: disable=invalid-name
    Project = apps.get_model("logger", "Project")  # noqa: N806

    def _set_project_perms():
        try:
            xform = XForm.objects.get(id=xform_id)
            project = Project.objects.get(id=project_id)
        except (Project.DoesNotExist, XForm.DoesNotExist) as e:
            msg = (
                f"{type(e)}: Setting project {project_id} permissions to "
                f"form {xform_id} failed."
            )
            # make a report only on the 3rd try.
            if self.request.retries > 2:
                report_exception(msg, e, sys.exc_info())
            self.retry(countdown=60 * self.request.retries, exc=e)
        else:
            set_project_perms_to_xform(xform, project)

            update_role_by_meta_xform_perms(xform)

            # Set MergedXForm permissions if XForm is also a MergedXForm
            if hasattr(xform, "mergedxform"):
                set_project_perms_to_xform(xform.mergedxform, project)

    try:
        if getattr(settings, "SLAVE_DATABASES", []):
            with use_master:
                _set_project_perms()
        else:
            _set_project_perms()
    except (Project.DoesNotExist, XForm.DoesNotExist) as e:
        # make a report only on the 3rd try.
        if self.request.retries > 2:
            msg = (
                f"{type(e)}: Setting project {project_id} permissions to "
                f"form {xform_id} failed."
            )
            report_exception(msg, e, sys.exc_info())
        # let's retry if the record may still not be available in read replica.
        self.retry(countdown=60 * self.request.retries)
    except IntegrityError:
        # Nothing to do, fail silently, permissions seems to have been applied
        # already.
        pass
    except Exception as e:  # pylint: disable=broad-except
        msg = (
            f"{type(e)}: Setting project {project_id} permissions to "
            f"form {xform_id} failed."
        )
        report_exception(msg, e, sys.exc_info())
