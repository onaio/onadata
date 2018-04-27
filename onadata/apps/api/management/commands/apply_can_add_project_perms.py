# -*- coding: utf-8 -*-
"""
Command apply_can_add_project_perms - applys can_add_project permission to all
users who have can_add_xform permission to a user/organization profile.

This was necessary because we previously (April 2018) did not have
can_add_project permission on the UserProfile and OrganizationProfile classes.
An attempt on doing this in migrations seems not to be a recommended approach.
"""
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from guardian.shortcuts import assign_perm

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.main.models import UserProfile


def org_can_add_project_permission():
    """
    Set 'can_add_project' permission to all users who have 'can_add_xform'
    permission in the organization profile.
    """
    organizations = OrganizationProfile.objects.all()

    for organization in organizations.iterator():
        permissions = organization.orgprofileuserobjectpermission_set.filter(
            permission__codename='can_add_xform')
        for permission in permissions:
            assign_perm('can_add_project', permission.user, organization)


def user_can_add_project_permission():
    """
    Set 'can_add_project' permission to all users who have 'can_add_xform'
    permission in the user profile.
    """
    users = UserProfile.objects.all()

    for user in users.iterator():
        permissions = user.userprofileuserobjectpermission_set.filter(
            permission__codename='can_add_xform')
        for permission in permissions:
            assign_perm('can_add_project', permission.user, user)


class Command(BaseCommand):
    """
    Command apply_can_add_preject_perms - applys can_add_project permission to
    all users who have can_add_xform permission to a user/organization profile.
    """
    help = _(u"Apply can_add_project permissions")

    def handle(self, *args, **options):
        user_can_add_project_permission()
        org_can_add_project_permission()
