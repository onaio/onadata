# -*- coding: utf-8 -*-
"""
OrganizationProfile module.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.utils.translation import gettext_lazy as _

from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase
from guardian.shortcuts import assign_perm, get_perms_for_model
from multidb.pinning import use_master

from onadata.apps.api.models.team import Team
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs.utils.cache_tools import IS_ORG, safe_delete
from onadata.libs.utils.common_tags import MEMBERS

User = get_user_model()


# pylint: disable=invalid-name,unused-argument
def org_profile_post_delete_callback(sender, instance, **kwargs):
    """
    Signal handler to delete the organization user object.
    """
    # delete the org_user too
    instance.user.delete()
    safe_delete(f"{IS_ORG}{instance.pk}")


def create_owner_team_and_assign_permissions(org):
    """
    Creates an Owner Team for a given organization and
    assigns the group and user permissions
    """
    team = Team.objects.create(
        name=Team.OWNER_TEAM_NAME, organization=org.user, created_by=org.created_by
    )
    content_type = ContentType.objects.get(app_label="api", model="organizationprofile")
    # pylint: disable=unpacking-non-sequence
    permission, _ = Permission.objects.get_or_create(
        codename="is_org_owner", name="Organization Owner", content_type=content_type
    )
    team.permissions.add(permission)
    org.creator.groups.add(team)

    for perm in get_perms_for_model(org.__class__):
        assign_perm(perm.codename, org.user, org)

        if org.creator:
            assign_perm(perm.codename, org.creator, org)

        if org.created_by and org.created_by != org.creator:
            assign_perm(perm.codename, org.created_by, org)

    if org.userprofile_ptr:
        for perm in get_perms_for_model(org.userprofile_ptr.__class__):
            assign_perm(perm.codename, org.user, org.userprofile_ptr)

            if org.creator:
                assign_perm(perm.codename, org.creator, org.userprofile_ptr)

            if org.created_by and org.created_by != org.creator:
                assign_perm(perm.codename, org.created_by, org.userprofile_ptr)

    return team


# pylint: disable=invalid-name
def get_or_create_organization_owners_team(org):
    """
    Get the owners team of an organization
    :param org: organization
    :return: Owners team of the organization
    """
    team_name = f"{org.user.username}#{Team.OWNER_TEAM_NAME}"
    try:
        team = Team.objects.get(name=team_name, organization=org.user)
    except Team.DoesNotExist:
        with use_master:
            queryset = Team.objects.filter(name=team_name, organization=org.user)
            if queryset.count() > 0:
                return queryset.first()  # pylint: disable=no-member
            return create_owner_team_and_assign_permissions(org)
    return team


def add_user_to_team(team, user):
    """
    Adds a user to a team and assigns them team permissions.
    """
    user.groups.add(team)

    # give the user perms to view the team
    assign_perm("view_team", user, team)

    # if team is owners team assign more perms
    if team.name.find(Team.OWNER_TEAM_NAME) > 0:
        _assign_organization_team_perms(team.organization, user)


def _assign_organization_team_perms(organization, user):
    owners_team = get_or_create_organization_owners_team(organization.profile)
    members_team = get_organization_members_team(organization.profile)
    for perm in get_perms_for_model(Team):
        assign_perm(perm.codename, user, owners_team)
        assign_perm(perm.codename, user, members_team)


def create_organization_team(organization, name, permission_names=None):
    """
    Creates an organization team with the given permissions as defined in
    permission_names.
    """
    organization = (
        organization.user
        if isinstance(organization, OrganizationProfile)
        else organization
    )
    team = Team.objects.create(organization=organization, name=name)
    content_type = ContentType.objects.get(app_label="api", model="organizationprofile")
    if permission_names:
        # get permission objects
        perms = Permission.objects.filter(
            codename__in=permission_names, content_type=content_type
        )
        if perms:
            team.permissions.add(*tuple(perms))
    return team


def get_organization_members_team(organization):
    """Get organization members team
    create members team if it does not exist and add organization owner
    to the members team"""
    try:
        team = Team.objects.get(name=f"{organization.user.username}#{MEMBERS}")
    except Team.DoesNotExist:
        team = create_organization_team(organization, MEMBERS)
        add_user_to_team(team, organization.user)

    return team


def _post_save_create_owner_team(sender, instance, created, **kwargs):
    """
    Signal handler that creates the Owner team and assigns group and user
    permissions.
    """
    if created:
        create_owner_team_and_assign_permissions(instance)


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
        app_label = "api"
        permissions = (
            ("can_add_project", "Can add a project to an organization"),
            ("can_add_xform", "Can add/upload an xform to an organization"),
        )

    is_organization = models.BooleanField(default=True)
    # Other fields here
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField(_("email address"), blank=True)

    def __str__(self):
        return f"{self.name}[{self.user.username}]"

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        super().save(*args, **kwargs)

    def remove_user_from_organization(self, user):
        """Removes a user from all teams/groups in the organization.

        :param user: The user to remove from this organization.
        """
        for group in user.groups.filter(name=f"{self.user.username}#"):
            user.groups.remove(group)

    def is_organization_owner(self, user):
        """Checks if user is in the organization owners team.

        :param user: User to check.

        :returns: Boolean whether user has organization level permissions.
        """
        has_owner_group = user.groups.filter(
            name=f"{self.user.username}#{Team.OWNER_TEAM_NAME}"
        )
        return has_owner_group.count() > 0


post_save.connect(
    _post_save_create_owner_team,
    sender=OrganizationProfile,
    dispatch_uid="create_owner_team_and_permissions",
)

post_delete.connect(
    org_profile_post_delete_callback,
    sender=OrganizationProfile,
    dispatch_uid="org_profile_post_delete_callback",
)


# pylint: disable=model-no-explicit-unicode
class OrgProfileUserObjectPermission(UserObjectPermissionBase):
    """Guardian model to create direct foreign keys."""

    content_object = models.ForeignKey(OrganizationProfile, on_delete=models.CASCADE)


class OrgProfileGroupObjectPermission(GroupObjectPermissionBase):
    """Guardian model to create direct foreign keys."""

    content_object = models.ForeignKey(OrganizationProfile, on_delete=models.CASCADE)
