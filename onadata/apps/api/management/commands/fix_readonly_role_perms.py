# -*- coding: utf-8 -*-
"""
fix_readonly_role_perms - Reassign permission to the model when permissions are changed
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _

from guardian.shortcuts import get_perms

from onadata.apps.api.models import Team
from onadata.libs.permissions import (
    DataEntryMinorRole,
    DataEntryOnlyRole,
    DataEntryRole,
    EditorMinorRole,
    EditorRole,
    ManagerRole,
    OwnerRole,
    ReadOnlyRole,
    ReadOnlyRoleNoDownload,
)
from onadata.libs.utils.model_tools import queryset_iterator

# pylint: disable=invalid-name
User = get_user_model()


def check_role(role_class, user, obj, new_perm=None):
    """
    Test if the user has the role for the object provided
    :param role_class:
    :param user:
    :param obj:
    :param new_perm:
    :return:
    """
    new_perm = new_perm if new_perm is None else []
    # remove the new permission because the old model doesnt have it
    perm_list = role_class.class_to_permissions[type(obj)]
    old_perm_set = set(perm_list)
    newly_added_perm = set(new_perm)

    if newly_added_perm.issubset(old_perm_set):
        diff_set = old_perm_set.difference(newly_added_perm)

        if isinstance(user, Team):
            return set(get_perms(user, obj)) == diff_set

        return user.has_perms(list(diff_set), obj)
    return False


def reassign_perms(user, model, new_perm):
    """
    Gets all the permissions the user has on objects and assigns the new
    permission to them
    :param user:
    :param model:
    :param new_perm:
    :return:
    """

    # Get the unique permission model objects filtered by content type
    #  for the user
    if isinstance(user, Team):
        if model == "project":
            objects = user.projectgroupobjectpermission_set.filter(
                group_id=user.pk
            ).distinct("content_object_id")
        else:
            objects = user.xformgroupobjectpermission_set.filter(
                group_id=user.pk
            ).distinct("content_object_id")
    else:
        if model == "project":
            objects = user.projectuserobjectpermission_set.all()
        else:
            objects = user.xformuserobjectpermission_set.all()

    for perm_obj in objects:
        obj = perm_obj.content_object
        roles = [
            ReadOnlyRoleNoDownload,
            ReadOnlyRole,
            DataEntryOnlyRole,
            DataEntryMinorRole,
            DataEntryRole,
            EditorMinorRole,
            EditorRole,
            ManagerRole,
            OwnerRole,
        ]

        # For each role reassign the perms
        for role_class in reversed(roles):
            not_readonly = role_class.user_has_role(user, obj) or role_class not in [
                ReadOnlyRoleNoDownload,
                ReadOnlyRole,
            ]
            if not_readonly:
                continue

            if check_role(role_class, user, obj, new_perm):
                # If true
                role_class.add(user, obj)
                break


class Command(BaseCommand):
    """
    fix_readonly_role_perms - Reassign permission to the model when
                              permissions are changed
    """

    args = "<app model [created_perm] >"
    help = _("Reassign permission to the model when permissions are changed")

    def handle(self, *args, **options):
        self.stdout.write("Re-assigining started", ending="\n")

        if not args:
            raise CommandError("Param not set. <app model [created_perm]>")

        if len(args) < 3:
            raise CommandError("Param not set. <app model [created_perm]>")

        model = args[1]
        username = args[2]
        new_perms = list(args[3:])

        if username == "all":
            users = User.objects.exclude(
                username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
            )

            teams = Team.objects.all()
        else:
            users = User.objects.filter(username=username)
            teams = Team.objects.filter(organization__username=username)
        # Get all the users
        for user in queryset_iterator(users):
            reassign_perms(user, model, new_perms)

        for team in queryset_iterator(teams):
            reassign_perms(team, model, new_perms)

        self.stdout.write("Re-assigining finished", ending="\n")
