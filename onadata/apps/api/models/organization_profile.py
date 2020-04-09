# -*- coding: utf-8 -*-
"""
OrganizationProfile module.
"""
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.utils.encoding import python_2_unicode_compatible

from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase
from guardian.shortcuts import assign_perm, get_perms_for_model

from onadata.apps.api.models.team import Team
from onadata.apps.main.models import UserProfile
from onadata.libs.utils.cache_tools import (
    IS_ORG, ORG_AVATAR_CACHE, safe_delete)


# pylint: disable=invalid-name,unused-argument
def org_profile_post_delete_callback(sender, instance, **kwargs):
    """
    Signal handler to delete the organization user object.
    """
    # delete the org_user too
    instance.user.delete()
    safe_delete('{}{}'.format(IS_ORG, instance.pk))


def create_owner_team_and_assign_permissions(org):
    """
    Creates an Owner Team for a given organization and
    assigns the group and user permissions
    """
    team = Team.objects.create(
        name=Team.OWNER_TEAM_NAME, organization=org.user,
        created_by=org.created_by)
    content_type = ContentType.objects.get(
        app_label='api', model='organizationprofile')
    # pylint: disable=unpacking-non-sequence
    permission, _ = Permission.objects.get_or_create(
        codename="is_org_owner", name="Organization Owner",
        content_type=content_type)  # pylint: disable=
    team.permissions.add(permission)
    org.creator.groups.add(team)

    for perm in get_perms_for_model(org.__class__):
        assign_perm(perm.codename, org.user, org)

        if org.creator:
            assign_perm(perm.codename, org.creator, org)

        if org.created_by and org.created_by != org.creator:
            assign_perm(perm.codename, org.created_by, org)

    if org.userprofile_ptr:
        for perm in get_perms_for_model(
                org.userprofile_ptr.__class__):
            assign_perm(
                perm.codename, org.user, org.userprofile_ptr)

            if org.creator:
                assign_perm(
                    perm.codename,
                    org.creator,
                    org.userprofile_ptr)

            if org.created_by and\
                    org.created_by != org.creator:
                assign_perm(
                    perm.codename,
                    org.created_by,
                    org.userprofile_ptr)

    return team


def _post_save_create_owner_team(sender, instance, created, **kwargs):
    """
    Signal handler that creates the Owner team and assigns group and user
    permissions.
    """
    if created:
        create_owner_team_and_assign_permissions(instance)


@python_2_unicode_compatible
class OrganizationProfile(UserProfile):

    """Organization: Extends the user profile for organization specific info

        * What does this do?
            - it has a createor
            - it has owner(s), through permissions/group
            - has members, through permissions/group
            - no login access, no password? no registration like a normal user?
            - created by a user who becomes the organization owner
        * What relationships?
    """

    class Meta:
        app_label = 'api'
        permissions = (
            ('can_add_project', "Can add a project to an organization"),
            ('can_add_xform', "Can add/upload an xform to an organization")
        )

    is_organization = models.BooleanField(default=True)
    # Other fields here
    creator = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return u'%s[%s]' % (self.name, self.user.username)

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        # set avatar url to cache
        # key should be <username>-org-avatar format
        if 'avatar-url' in self.metadata:
            cache.set(f'{self.user.username}{ORG_AVATAR_CACHE}', self.metadata['avatar-url'])
        super(OrganizationProfile, self).save(*args, **kwargs)

    def remove_user_from_organization(self, user):
        """Removes a user from all teams/groups in the organization.

        :param user: The user to remove from this organization.
        """
        for group in user.groups.filter('%s#' % self.user.username):
            user.groups.remove(group)

    def is_organization_owner(self, user):
        """Checks if user is in the organization owners team.

        :param user: User to check.

        :returns: Boolean whether user has organization level permissions.
        """
        has_owner_group = user.groups.filter(
            name='%s#%s' % (self.user.username, Team.OWNER_TEAM_NAME))
        return True if has_owner_group else False


post_save.connect(
    _post_save_create_owner_team, sender=OrganizationProfile,
    dispatch_uid='create_owner_team_and_permissions')

post_delete.connect(org_profile_post_delete_callback,
                    sender=OrganizationProfile,
                    dispatch_uid='org_profile_post_delete_callback')


# pylint: disable=model-no-explicit-unicode
class OrgProfileUserObjectPermission(UserObjectPermissionBase):
    """Guardian model to create direct foreign keys."""
    content_object = models.ForeignKey(
        OrganizationProfile, on_delete=models.CASCADE)


class OrgProfileGroupObjectPermission(GroupObjectPermissionBase):
    """Guardian model to create direct foreign keys."""
    content_object = models.ForeignKey(
        OrganizationProfile, on_delete=models.CASCADE)
