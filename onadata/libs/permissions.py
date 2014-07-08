from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import \
    assign_perm, remove_perm, \
    get_users_with_perms, get_perms
from onadata.apps.api.models import OrganizationProfile
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.logger.models import XForm
from onadata.apps.api.models import Project

CAN_ADD_XFORM_TO_PROFILE = 'can_add_xform'
CAN_VIEW_PROFILE = 'view_profile'
CAN_CHANGE_XFORM = 'change_xform'
CAN_ADD_XFORM = 'add_xform'
CAN_DELETE_XFORM = 'delete_xform'
CAN_VIEW_XFORM = 'view_xform'
CAN_ADD_SUBMISSIONS = 'report_xform'
CAN_TRANSFER_OWNERSHIP = 'transfer_xform'
CAN_MOVE_TO_FOLDER = 'move_xform'

# Project Permissions
CAN_VIEW_PROJECT = 'view_project'
CAN_CHANGE_PROJECT = 'change_project'
CAN_TRANSFER_PROJECT_OWNERSHIP = 'transfer_project'
CAN_DELETE_PROJECT = 'delete_project'


class Role(object):
    permissions = None
    name = None

    @classmethod
    def _remove_obj_permissions(self, user, obj):
        content_type = ContentType.objects.get(
            model=obj.__class__.__name__.lower(),
            app_label=obj.__class__._meta.app_label
        )
        object_permissions = user.userobjectpermission_set.filter(
            object_pk=obj.pk, content_type=content_type)

        for perm in object_permissions:
            remove_perm(perm.permission.codename, user, obj)

    @classmethod
    def add(cls, user, obj):
        cls._remove_obj_permissions(user, obj)

        for codename, klass in cls.permissions:
            if isinstance(obj, klass):
                assign_perm(codename, user, obj)

    @classmethod
    def has_role(cls, user, obj):
        """Check that a user has this role"""
        has_perms = False

        for permission, klass in cls.permissions:
            if isinstance(obj, klass):
                if not user.has_perm(permission, obj):
                    return False

                has_perms = True

        return has_perms


class ReadOnlyRole(Role):
    name = 'readonly'
    permissions = (
        (CAN_VIEW_XFORM, XForm),
        (CAN_VIEW_PROJECT, Project)
    )


class DataEntryRole(Role):
    name = 'dataentry'
    permissions = (
        (CAN_VIEW_XFORM, XForm),
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_XFORM, Project)
    )


class EditorRole(Role):
    name = 'editor'
    permissions = (
        (CAN_VIEW_XFORM, XForm),
        (CAN_ADD_SUBMISSIONS, XForm),
        (CAN_CHANGE_XFORM, XForm),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_XFORM, Project),
        (CAN_CHANGE_PROJECT, Project)
    )


class ManagerRole(Role):
    name = 'manager'
    permissions = (
        (CAN_ADD_XFORM_TO_PROFILE, (UserProfile, OrganizationProfile)),
        (CAN_VIEW_PROFILE, UserProfile),
        (CAN_ADD_XFORM, XForm),
        (CAN_VIEW_XFORM, XForm),
        (CAN_CHANGE_XFORM, XForm),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_XFORM, Project),
        (CAN_CHANGE_PROJECT, Project),
        (CAN_DELETE_PROJECT, Project)
    )


class OwnerRole(Role):
    name = 'owner'
    permissions = (
        (CAN_ADD_XFORM_TO_PROFILE, (UserProfile, OrganizationProfile)),
        (CAN_VIEW_PROFILE, UserProfile),
        (CAN_ADD_XFORM, XForm),
        (CAN_VIEW_XFORM, XForm),
        (CAN_CHANGE_XFORM, XForm),
        (CAN_DELETE_XFORM, XForm),
        (CAN_MOVE_TO_FOLDER, XForm),
        (CAN_TRANSFER_OWNERSHIP, XForm),
        (CAN_VIEW_PROJECT, Project),
        (CAN_ADD_XFORM, Project),
        (CAN_CHANGE_PROJECT, Project),
        (CAN_DELETE_PROJECT, Project),
        (CAN_TRANSFER_PROJECT_OWNERSHIP, Project)
    )

ROLES = {role.name: role for role in [ReadOnlyRole,
                                      DataEntryRole,
                                      EditorRole,
                                      ManagerRole,
                                      OwnerRole]}


def get_role(self, obj):
    for role in ROLES.values():
        if role.has_role(self, obj):
                return role.name


def get_object_users_with_permissions(obj):
    """
    Returns users, roles and permissions for a object
    """
    users_with_perms = []
    if obj:
        for user in get_users_with_perms(obj):
            user_permissions = {'user': user,
                                'role': get_role(user, obj),
                                'permissions': get_perms(user, obj)}
            users_with_perms.append(user_permissions)
    return users_with_perms
