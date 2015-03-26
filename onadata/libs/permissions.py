from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import (
    assign_perm,
    remove_perm,
    get_perms,
    get_users_with_perms)

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.api.models.team import Team
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.logger.models import Project
from onadata.apps.logger.models import XForm

# Userprofile Permissions
CAN_ADD_USERPROFILE = 'add_userprofile'
CAN_CHANGE_USERPROFILE = 'change_userprofile'
CAN_DELETE_USERPROFILE = 'delete_userprofile'
CAN_ADD_XFORM_TO_PROFILE = 'can_add_xform'
CAN_VIEW_PROFILE = 'view_profile'

# Organization Permissions
CAN_VIEW_ORGANIZATION_PROFILE = 'view_organizationprofile'
CAN_ADD_ORGANIZATION_PROFILE = 'add_organizationprofile'
CAN_ADD_ORGANIZATION_XFORM = 'can_add_xform'
CAN_CHANGE_ORGANIZATION_PROFILE = 'change_organizationprofile'
CAN_DELETE_ORGANIZATION_PROFILE = 'delete_organizationprofile'
IS_ORGANIZATION_OWNER = 'is_org_owner'

# Xform Permissions
CAN_CHANGE_XFORM = 'change_xform'
CAN_ADD_XFORM = 'add_xform'
CAN_DELETE_XFORM = 'delete_xform'
CAN_VIEW_XFORM = 'view_xform'
CAN_ADD_SUBMISSIONS = 'report_xform'
CAN_TRANSFER_OWNERSHIP = 'transfer_xform'
CAN_MOVE_TO_FOLDER = 'move_xform'

# Project Permissions
CAN_ADD_PROJECT = 'add_project'
CAN_VIEW_PROJECT = 'view_project'
CAN_CHANGE_PROJECT = 'change_project'
CAN_TRANSFER_PROJECT_OWNERSHIP = 'transfer_project'
CAN_DELETE_PROJECT = 'delete_project'
CAN_ADD_PROJECT_XFORM = 'add_project_xform'
CAN_ADD_SUBMISSIONS_PROJECT = 'report_project_xform'

CAN_ADD_DATADICTIONARY = 'add_datadictionary'
CAN_CHANGE_DATADICTIONARY = 'change_datadictionary'
CAN_DELETE_DATADICTIONARY = 'delete_datadictionary'


class Role(object):
    class_to_permissions = None
    permissions = None
    name = None

    @classmethod
    def _remove_obj_permissions(cls, user, obj):
        content_type = ContentType.objects.get(
            model=obj.__class__.__name__.lower(),
            app_label=obj.__class__._meta.app_label
        )
        if isinstance(user, Team):
            object_permissions = user.groupobjectpermission_set.filter(
                object_pk=obj.pk, content_type=content_type)
        else:
            object_permissions = user.userobjectpermission_set.filter(
                object_pk=obj.pk, content_type=content_type)

        for perm in object_permissions:
            remove_perm(perm.permission.codename, user, obj)

    @classmethod
    def add(cls, user, obj):
        cls._remove_obj_permissions(user, obj)

        for codename, klass in cls.permissions:
            if type(obj) == klass:
                assign_perm(codename, user, obj)

    @classmethod
    def has_role(cls, permissions, obj):
        """Check that permission correspond to this role for this object.

        :param permissions: A list of permissions.
        :param obj: An object to get the permissions of.
        """
        perms_for_role = set(cls.class_to_permissions[type(obj)])

        return perms_for_role.issubset(set(permissions))

    @classmethod
    def user_has_role(cls, user, obj):
        """Check that a user has this role.

        :param user: A user object.
        :param obj: An object to get the permissions of.
        """
        return user.has_perms(cls.class_to_permissions[type(obj)], obj)


class ReadOnlyRole(Role):
    name = 'readonly'
    permissions = (
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_VIEW_XFORM, XForm),
        (CAN_VIEW_PROJECT, Project),
    )


class DataEntryRole(Role):
    name = 'dataentry'
    permissions = (
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_VIEW_XFORM, XForm),
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_SUBMISSIONS_PROJECT, Project),
    )


class EditorRole(Role):
    name = 'editor'
    permissions = (
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_CHANGE_XFORM, XForm),
        (CAN_VIEW_XFORM, XForm),
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_CHANGE_PROJECT, Project),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_SUBMISSIONS_PROJECT, Project),
    )


class ManagerRole(Role):
    name = 'manager'
    permissions = (
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_ADD_XFORM, XForm),
        (CAN_CHANGE_XFORM, XForm),
        (CAN_VIEW_XFORM, XForm),
        (CAN_DELETE_XFORM, XForm),
        (CAN_ADD_XFORM_TO_PROFILE, OrganizationProfile),
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_ADD_XFORM_TO_PROFILE, UserProfile),
        (CAN_VIEW_PROFILE, UserProfile),
        (CAN_ADD_PROJECT, Project),
        (CAN_ADD_PROJECT_XFORM, Project),
        (CAN_CHANGE_PROJECT, Project),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_SUBMISSIONS_PROJECT, Project),
    )


class MemberRole(Role):

    """This is a role for a member of an organization.
    """
    name = 'member'


class OwnerRole(Role):

    """This is a role for an owner of a dataset, organization, or project.
    """
    name = 'owner'
    permissions = (
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_ADD_XFORM, XForm),
        (CAN_VIEW_XFORM, XForm),
        (CAN_ADD_DATADICTIONARY, XForm),
        (CAN_CHANGE_DATADICTIONARY, XForm),
        (CAN_DELETE_DATADICTIONARY, XForm),
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_DELETE_XFORM, XForm),
        (CAN_MOVE_TO_FOLDER, XForm),
        (CAN_TRANSFER_OWNERSHIP, XForm),
        (CAN_CHANGE_XFORM, XForm),
        (CAN_ADD_XFORM_TO_PROFILE, UserProfile),
        (CAN_ADD_USERPROFILE, UserProfile),
        (CAN_CHANGE_USERPROFILE, UserProfile),
        (CAN_DELETE_USERPROFILE, UserProfile),
        (CAN_ADD_XFORM_TO_PROFILE, UserProfile),
        (CAN_VIEW_PROFILE, UserProfile),
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_ADD_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_ADD_ORGANIZATION_XFORM, OrganizationProfile),
        (CAN_CHANGE_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_DELETE_ORGANIZATION_PROFILE, OrganizationProfile),
        (IS_ORGANIZATION_OWNER, OrganizationProfile),
        (CAN_ADD_XFORM_TO_PROFILE, OrganizationProfile),
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_ADD_PROJECT, Project),
        (CAN_ADD_PROJECT_XFORM, Project),
        (CAN_CHANGE_PROJECT, Project),
        (CAN_DELETE_PROJECT, Project),
        (CAN_TRANSFER_PROJECT_OWNERSHIP, Project),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_SUBMISSIONS_PROJECT, Project),
    )

ROLES_ORDERED = [ReadOnlyRole,
                 DataEntryRole,
                 EditorRole,
                 ManagerRole,
                 OwnerRole]

ROLES = {role.name: role for role in ROLES_ORDERED}

# Memoize a class to permissions dict.
for role in ROLES.values():
    role.class_to_permissions = defaultdict(list)
    [role.class_to_permissions[k].append(p) for p, k in role.permissions]


def is_organization(obj):
    try:
        obj.organizationprofile
        return True
    except OrganizationProfile.DoesNotExist:
        return False


def get_role(permissions, obj):
    for role in reversed(ROLES_ORDERED):
        if role.has_role(permissions, obj):
            return role.name


def get_role_in_org(user, organization):
    perms = get_perms(user, organization)

    if 'is_org_owner' in perms:
        return OwnerRole.name
    else:
        return get_role(perms, organization) or MemberRole.name


def get_object_users_with_permissions(obj, exclude=None):
    """Returns users, roles and permissions for a object.
    """
    result = []

    if obj:
        users_with_perms = get_users_with_perms(
            obj, attach_perms=True, with_group_users=False).items()

        result = [{
            'user': user,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': get_role(permissions, obj),
            'gravatar': user.profile.gravatar,
            'metadata': user.profile.metadata,
            'permissions': permissions} for user, permissions in
            users_with_perms]

    return result


def get_team_project_default_permissions(team, project):
    perms = get_perms(team, project)

    return get_role(perms, project) or ""
