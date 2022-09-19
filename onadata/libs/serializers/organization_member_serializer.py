# -*- coding: utf-8 -*-
"""
The OrganizationMemberSerializer - manages a users access in an organization
"""
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils.translation import gettext as _

from rest_framework import serializers

from onadata.apps.api.tools import (
    _get_owners,
    add_user_to_organization,
    add_user_to_team,
    get_or_create_organization_owners_team,
    get_organization_members,
    remove_user_from_organization,
    remove_user_from_team,
)
from onadata.libs.models.share_project import ShareProject
from onadata.libs.permissions import ROLES, OwnerRole, is_organization
from onadata.libs.serializers.fields.organization_field import OrganizationField
from onadata.settings.common import DEFAULT_FROM_EMAIL, SHARE_ORG_SUBJECT

User = get_user_model()


def _compose_send_email(organization, user, email_msg, email_subject=None):

    if not email_subject:
        email_subject = SHARE_ORG_SUBJECT.format(user.username, organization.name)

    # send out email message.
    send_mail(email_subject, email_msg, DEFAULT_FROM_EMAIL, (user.email,))


def _set_organization_role_to_user(organization, user, role):
    role_cls = ROLES.get(role)
    role_cls.add(user, organization)

    owners_team = get_or_create_organization_owners_team(organization)

    # add the owner to owners team
    if role == OwnerRole.name:
        role_cls.add(user, organization.userprofile_ptr)
        add_user_to_team(owners_team, user)
        # add user to org projects
        for project in organization.user.project_org.all():
            ShareProject(project, user.username, role).save()

    if role != OwnerRole.name:
        remove_user_from_team(owners_team, user)


class OrganizationMemberSerializer(serializers.Serializer):
    """
    The OrganizationMemberSerializer - manages a users access in an organization
    """

    organization = OrganizationField()
    username = serializers.CharField(max_length=255, required=False)
    role = serializers.CharField(max_length=50, required=False)
    email_msg = serializers.CharField(max_length=1024, required=False)
    email_subject = serializers.CharField(max_length=255, required=False)
    remove = serializers.BooleanField(default=False)

    def update(self, instance, validated_data):
        # Do nothing
        pass

    def validate_username(self, value):
        """Check that the username exists"""

        user = None
        try:
            user = User.objects.get(username=value)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError(
                _(f"User '{value}' does not exist.")
            ) from exc
        else:
            if not user.is_active:
                raise serializers.ValidationError(_("User is not active"))

            if is_organization(user.profile):
                raise serializers.ValidationError(
                    _(f"Cannot add org account `{user.username}` as member.")
                )

        return value

    def validate_role(self, value):
        """check that the role exists"""
        if value not in ROLES:
            raise serializers.ValidationError(_(f"Unknown role '{value}'."))

        return value

    def validate(self, attrs):
        remove = attrs.get("remove")
        role = attrs.get("role")
        organization = attrs.get("organization")
        username = attrs.get("username")

        # check if roles are downgrading and the user is the last admin
        if username and (remove or role != OwnerRole.name):
            user = User.objects.get(username=username)

            owners = _get_owners(organization)
            if user in owners and len(owners) <= 1:
                raise serializers.ValidationError(
                    _("Organization cannot be without an owner")
                )

        return attrs

    def create(self, validated_data):
        organization = validated_data.get("organization")
        username = validated_data.get("username")
        role = validated_data.get("role")
        email_msg = validated_data.get("email_msg")
        email_subject = validated_data.get("email_subject")
        remove = validated_data.get("remove")

        if username:
            user = User.objects.get(username=username)

            add_user_to_organization(organization, user)

            if role:
                _set_organization_role_to_user(organization, user, role)

            if email_msg:
                _compose_send_email(organization, user, email_msg, email_subject)

            if remove:
                remove_user_from_organization(organization, user)

        return organization

    @property
    def data(self):
        organization = self.validated_data.get("organization")
        members = get_organization_members(organization)
        return [u.username for u in members]
