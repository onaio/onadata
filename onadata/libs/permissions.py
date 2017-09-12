import json
from collections import defaultdict

import six
from guardian.shortcuts import (assign_perm, get_perms, remove_perm,
                                get_users_with_perms)

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.logger.models import MergedXForm, Project, XForm
from onadata.apps.logger.models.project import (ProjectUserObjectPermission,
                                                ProjectGroupObjectPermission)
from onadata.apps.logger.models.xform import (XFormUserObjectPermission,
                                              XFormGroupObjectPermission)
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs.exceptions import NoRecordsPermission
from onadata.libs.utils.common_tags import XFORM_META_PERMS

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
CAN_VIEW_XFORM_DATA = 'view_xform_data'
CAN_VIEW_XFORM_ALL = 'view_xform_all'
CAN_ADD_SUBMISSIONS = 'report_xform'
CAN_DELETE_SUBMISSION = 'delete_submission'
CAN_TRANSFER_OWNERSHIP = 'transfer_xform'
CAN_MOVE_TO_FOLDER = 'move_xform'
CAN_EXPORT_XFORM = 'can_export_xform_data'

# MergedXform Permissions
CAN_VIEW_MERGED_XFORM = 'view_mergedxform'

# Project Permissions
CAN_ADD_PROJECT = 'add_project'
CAN_VIEW_PROJECT = 'view_project'
CAN_VIEW_PROJECT_DATA = 'view_project_data'
CAN_VIEW_PROJECT_ALL = 'view_project_all'
CAN_CHANGE_PROJECT = 'change_project'
CAN_TRANSFER_PROJECT_OWNERSHIP = 'transfer_project'
CAN_DELETE_PROJECT = 'delete_project'
CAN_ADD_PROJECT_XFORM = 'add_project_xform'
CAN_ADD_SUBMISSIONS_PROJECT = 'report_project_xform'
CAN_EXPORT_PROJECT = 'can_export_project_data'

# Data dictionary permissions
CAN_ADD_DATADICTIONARY = 'add_datadictionary'
CAN_CHANGE_DATADICTIONARY = 'change_datadictionary'
CAN_DELETE_DATADICTIONARY = 'delete_datadictionary'


class Role(object):
    class_to_permissions = None
    permissions = None
    name = None

    @classmethod
    def _remove_obj_permissions(cls, user, obj):
        for perm in get_perms(user, obj):
            remove_perm(perm, user, obj)

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


class ReadOnlyRoleNoDownload(Role):
    name = 'readonly-no-download'
    permissions = (
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_VIEW_XFORM, XForm),
        (CAN_VIEW_PROJECT, Project),
        (CAN_VIEW_XFORM_ALL, XForm),
        (CAN_VIEW_PROJECT_ALL, Project),
        (CAN_VIEW_MERGED_XFORM, MergedXForm), )


class ReadOnlyRole(Role):
    name = 'readonly'
    permissions = (
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_VIEW_XFORM, XForm),
        (CAN_VIEW_PROJECT, Project),
        (CAN_EXPORT_XFORM, XForm),
        (CAN_EXPORT_PROJECT, Project),
        (CAN_VIEW_XFORM_ALL, XForm),
        (CAN_VIEW_PROJECT_ALL, Project),
        (CAN_VIEW_MERGED_XFORM, MergedXForm), )


class DataEntryOnlyRole(Role):
    name = 'dataentry-only'
    permissions = (
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_VIEW_XFORM, XForm),
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_SUBMISSIONS_PROJECT, Project),
        (CAN_EXPORT_XFORM, XForm),
        (CAN_EXPORT_PROJECT, Project),
        (CAN_VIEW_MERGED_XFORM, MergedXForm), )


class DataEntryMinorRole(Role):
    name = 'dataentry-minor'
    permissions = (
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_VIEW_XFORM, XForm),
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_SUBMISSIONS_PROJECT, Project),
        (CAN_EXPORT_XFORM, XForm),
        (CAN_EXPORT_PROJECT, Project),
        (CAN_VIEW_XFORM_DATA, XForm),
        (CAN_VIEW_PROJECT_DATA, Project),
        (CAN_VIEW_MERGED_XFORM, MergedXForm), )


class DataEntryRole(Role):
    name = 'dataentry'
    permissions = (
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_VIEW_XFORM, XForm),
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_SUBMISSIONS_PROJECT, Project),
        (CAN_EXPORT_XFORM, XForm),
        (CAN_EXPORT_PROJECT, Project),
        (CAN_VIEW_XFORM_ALL, XForm),
        (CAN_VIEW_XFORM_DATA, XForm),
        (CAN_VIEW_PROJECT_DATA, Project),
        (CAN_VIEW_PROJECT_ALL, Project),
        (CAN_VIEW_MERGED_XFORM, MergedXForm), )


class EditorMinorRole(Role):
    name = 'editor-minor'
    permissions = (
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_CHANGE_XFORM, XForm),
        (CAN_VIEW_XFORM, XForm),
        (CAN_DELETE_SUBMISSION, XForm),
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_CHANGE_PROJECT, Project),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_SUBMISSIONS_PROJECT, Project),
        (CAN_EXPORT_XFORM, XForm),
        (CAN_EXPORT_PROJECT, Project),
        (CAN_VIEW_XFORM_DATA, XForm),
        (CAN_VIEW_PROJECT_DATA, Project),
        (CAN_VIEW_MERGED_XFORM, MergedXForm), )


class EditorRole(Role):
    name = 'editor'
    permissions = (
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_CHANGE_XFORM, XForm),
        (CAN_VIEW_XFORM, XForm),
        (CAN_DELETE_SUBMISSION, XForm),
        (CAN_VIEW_ORGANIZATION_PROFILE, OrganizationProfile),
        (CAN_CHANGE_PROJECT, Project),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_SUBMISSIONS_PROJECT, Project),
        (CAN_EXPORT_XFORM, XForm),
        (CAN_EXPORT_PROJECT, Project),
        (CAN_VIEW_XFORM_ALL, XForm),
        (CAN_VIEW_XFORM_DATA, XForm),
        (CAN_VIEW_PROJECT_DATA, Project),
        (CAN_VIEW_PROJECT_ALL, Project),
        (CAN_VIEW_MERGED_XFORM, MergedXForm), )


class ManagerRole(Role):
    name = 'manager'
    permissions = (
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_ADD_XFORM, XForm),
        (CAN_CHANGE_XFORM, XForm),
        (CAN_VIEW_XFORM, XForm),
        (CAN_DELETE_SUBMISSION, XForm),
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
        (CAN_EXPORT_XFORM, XForm),
        (CAN_EXPORT_PROJECT, Project),
        (CAN_VIEW_XFORM_ALL, XForm),
        (CAN_VIEW_XFORM_DATA, XForm),
        (CAN_VIEW_PROJECT_DATA, Project),
        (CAN_VIEW_PROJECT_ALL, Project),
        (CAN_VIEW_MERGED_XFORM, MergedXForm), )


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
        (CAN_DELETE_SUBMISSION, XForm),
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
        (CAN_EXPORT_XFORM, XForm),
        (CAN_EXPORT_PROJECT, Project),
        (CAN_VIEW_XFORM_ALL, XForm),
        (CAN_VIEW_XFORM_DATA, XForm),
        (CAN_VIEW_PROJECT_DATA, Project),
        (CAN_VIEW_PROJECT_ALL, Project),
        (CAN_VIEW_MERGED_XFORM, MergedXForm))


ROLES_ORDERED = [
    ReadOnlyRoleNoDownload, ReadOnlyRole, DataEntryOnlyRole,
    DataEntryMinorRole, DataEntryRole, EditorMinorRole, EditorRole,
    ManagerRole, OwnerRole
]

ROLES = {role.name: role for role in ROLES_ORDERED}

# Memoize a class to permissions dict.
for role in ROLES.values():
    role.class_to_permissions = defaultdict(list)
    [role.class_to_permissions[k].append(p) for p, k in role.permissions]


def is_organization(obj):
    """Some OrganizationProfiles have a pointer to the UserProfile, but no
    UserProfiles do. Check for that first since it avoids a database hit.
    """
    try:
        hasattr(obj, 'userprofile_ptr') or obj.organizationprofile
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


def _get_group_users_with_perms(obj, attach_perms=False, user_perms=None):
    """
    Returns a list of users in the groups with permissions on the object obj.
    """
    if isinstance(obj, XForm):
        Klass = XFormGroupObjectPermission  # pylint: disable=C0103
    elif isinstance(obj, Project):
        Klass = ProjectGroupObjectPermission  # pylint: disable=C0103
    else:
        return get_users_with_perms(obj, attach_perms=attach_perms,
                                    with_group_users=True)
    group_obj_perms = Klass.objects.filter(content_object_id=obj.pk)
    group_users = {}
    if attach_perms:
        if user_perms:
            group_users.update(user_perms)
        _cache = {}
        for perm in group_obj_perms:
            if perm.group not in _cache:
                _cache[perm.group] = perm.group.user_set.all()
            for user in _cache[perm.group]:
                if user in group_users:
                    group_users[user].add(perm.permission.codename)
                else:
                    group_users[user] = set([perm.permission.codename])
    else:
        group_users = set() if not user_perms else set(user_perms)
        for perm in group_obj_perms.distinct('group'):
            group_users.union(set([user for user in
                                   perm.group.user_set.all()]))
        group_users = list(group_obj_perms)

    return group_users


def _get_users_with_perms(obj, attach_perms=False, with_group_users=None):
    """
    Returns a list of users with their permissions on an object obj.
    """
    if isinstance(obj, XForm):
        Klass = XFormUserObjectPermission  # pylint: disable=C0103
    elif isinstance(obj, Project):
        Klass = ProjectUserObjectPermission  # pylint: disable=C0103
    else:
        return get_users_with_perms(obj, attach_perms=attach_perms,
                                    with_group_users=with_group_users)
    user_obj_perms = Klass.objects.filter(content_object_id=obj.pk)
    user_perms = {}
    if attach_perms:
        for perm in user_obj_perms:
            if perm.user in user_perms:
                user_perms[perm.user].add(perm.permission.codename)
            else:
                user_perms[perm.user] = set([perm.permission.codename])
    else:
        user_perms = [
            perm.user for perm in user_obj_perms.only('user').distinct('user')]

    if with_group_users:
        user_perms = _get_group_users_with_perms(obj, attach_perms, user_perms)

    return user_perms


def get_object_users_with_permissions(obj,
                                      username=False,
                                      with_group_users=False):
    """
    Returns users, roles and permissions for an object.

    :param obj: object, the object to check permissions on
    :param username: bool, when True set username instead of a User object
    """
    result = []

    if obj:
        users_with_perms = _get_users_with_perms(
            obj, attach_perms=True, with_group_users=with_group_users).items()

        result = [{
            'user': user.username if username else user,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': get_role(permissions, obj),
            'is_org': is_organization(user.profile),
            'gravatar': user.profile.gravatar,
            'metadata': user.profile.metadata
        } for user, permissions in users_with_perms]

    return result


def get_team_project_default_permissions(team, project):
    perms = get_perms(team, project)

    return get_role(perms, project) or ""


def _check_meta_perms_enabled(xform):
    """
        Check for meta-perms settings in the xform metadata model.
        :param xform:
        :return: bool
    """
    return xform.metadata_set.filter(data_type=XFORM_META_PERMS).count() > 0


def filter_queryset_xform_meta_perms(xform, user, instance_queryset):
    """
        Check for the specific perms if meta-perms have been enabled
        CAN_VIEW_XFORM_ALL ==> User should be able to view all the data
        CAN_VIEW_XFORM_DATA ===> User should be able to view his/her submitted
        data.  Otherwise should raise forbidden error.
        :param xform:
        :param user:
        :param instance_queryset:
        :return: data
    """
    if user.has_perm(CAN_VIEW_XFORM_ALL, xform) or xform.shared_data  \
            or not _check_meta_perms_enabled(xform):
        return instance_queryset
    elif user.has_perm(CAN_VIEW_XFORM_DATA, xform):
        return instance_queryset.filter(user=user)
    else:
        return instance_queryset.none()


def filter_queryset_xform_meta_perms_sql(xform, user, query):
    """
        Check for the specific perms if meta-perms have been enabled
        CAN_VIEW_XFORM_ALL ==> User should be able to view all the data
        CAN_VIEW_XFORM_DATA ===> User should be able to view his/her submitted
         data. Otherwise should raise forbidden error.
        :param xform:
        :param user:
        :param instance_queryset:
        :return: data
        """
    if user.has_perm(CAN_VIEW_XFORM_ALL, xform) or xform.shared_data\
            or not _check_meta_perms_enabled(xform):
        ret_query = query
    elif user.has_perm(CAN_VIEW_XFORM_DATA, xform):
        try:
            if query and isinstance(query, six.string_types):
                query = json.loads(query)
                if isinstance(query, list):
                    query = query[0]
            else:
                query = dict()

            query.update({"_submitted_by": user.username})
            ret_query = json.dumps(query)

        except (ValueError, AttributeError):
            query_list = list()
            query_list.append({"_submitted_by": user.username})
            query_list.append(query)

            ret_query = json.dumps(query_list)
    else:
        raise NoRecordsPermission()

    return ret_query
