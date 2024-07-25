# -*- coding: utf-8 -*-
"""
Project invitations serializer
"""
import re
from django.conf import settings
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from onadata.apps.logger.models import ProjectInvitation
from onadata.libs.permissions import ROLES
from onadata.apps.api.tasks import send_project_invitation_email_async
from onadata.libs.utils.email import get_project_invitation_url


User = get_user_model()


class ProjectInvitationSerializer(serializers.ModelSerializer):
    """Serializer for ProjectInvitation model object"""

    class Meta:
        model = ProjectInvitation
        fields = (
            "id",
            "email",
            "project",
            "role",
            "status",
        )
        read_only_fields = ("status",)
        extra_kwargs = {"project": {"write_only": True}}

    def validate_email(self, email):
        """Validate `email` field"""
        # Regular expression pattern for email validation
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        err_msg = "Invalid email."

        # Check if the email matches the pattern
        if not re.match(pattern, email):
            raise serializers.ValidationError(_(err_msg))

        domain_whitelist = getattr(
            settings, "PROJECT_INVITATION_EMAIL_DOMAIN_WHITELIST", []
        )

        if domain_whitelist:
            # Extract the domain from the email address
            domain = email.split("@")[1]

            # Check if the domain matches "foo.com"
            if not domain.lower() in [
                allowed_domain.lower() for allowed_domain in domain_whitelist
            ]:
                raise serializers.ValidationError(_(err_msg))

        return email

    def validate_role(self, role):
        """Validate `role` field"""
        if role not in ROLES:
            raise serializers.ValidationError(_("Invalid role."))

        return role

    def _validate_email_exists(self, email):
        """Email should not be of an existing user"""
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(_("User already exists"))

    def _send_project_invitation_email(self, invitation_id: str) -> None:
        """Send project invitation email"""
        project_activation_url = get_project_invitation_url(self.context["request"])
        send_project_invitation_email_async.delay(invitation_id, project_activation_url)

    def create(self, validated_data):
        if ProjectInvitation.objects.filter(
            email=validated_data["email"],
            project=validated_data["project"],
            status=ProjectInvitation.Status.PENDING,
        ).exists():
            raise serializers.ValidationError(_("Invitation already exists."))

        self._validate_email_exists(validated_data["email"])
        instance = super().create(validated_data)
        instance.invited_by = self.context["request"].user
        instance.save()
        self._send_project_invitation_email(instance.id)

        return instance

    def update(self, instance, validated_data):
        # only a pending invitation can be updated
        if instance.status != ProjectInvitation.Status.PENDING:
            raise serializers.ValidationError(
                _("Only pending invitations can be updated")
            )

        self._validate_email_exists(validated_data["email"])
        has_email_changed = instance.email != validated_data["email"]
        updated_instance = super().update(instance, validated_data)

        if has_email_changed:
            self._send_project_invitation_email(instance.id)

        return updated_instance


# pylint: disable=abstract-method
class ProjectInvitationUpdateBaseSerializer(serializers.Serializer):
    """Base serializer for project invitation updates"""

    invitation_id = serializers.IntegerField()

    def validate_invitation_id(self, invitation_id):
        """Validate `invitation_id` field"""
        try:
            ProjectInvitation.objects.get(pk=invitation_id)

        except ProjectInvitation.DoesNotExist as error:
            raise serializers.ValidationError(_("Invalid invitation_id.")) from error

        return invitation_id


class ProjectInvitationRevokeSerializer(ProjectInvitationUpdateBaseSerializer):
    """Serializer for revoking a project invitation"""

    def validate_invitation_id(self, invitation_id):
        super().validate_invitation_id(invitation_id)

        invitation = ProjectInvitation.objects.get(pk=invitation_id)

        if invitation.status != ProjectInvitation.Status.PENDING:
            raise serializers.ValidationError(
                _("You cannot revoke an invitation which is not pending")
            )

        return invitation_id

    def save(self, **kwargs):
        invitation_id = self.validated_data.get("invitation_id")
        invitation = ProjectInvitation.objects.get(pk=invitation_id)
        invitation.revoke()


class ProjectInvitationResendSerializer(ProjectInvitationUpdateBaseSerializer):
    """Serializer for resending a project invitation"""

    def validate_invitation_id(self, invitation_id):
        super().validate_invitation_id(invitation_id)

        invitation = ProjectInvitation.objects.get(pk=invitation_id)

        if invitation.status != ProjectInvitation.Status.PENDING:
            raise serializers.ValidationError(
                _("You cannot resend an invitation which is not pending")
            )

        return invitation_id

    def save(self, **kwargs):
        invitation_id = self.validated_data.get("invitation_id")
        invitation = ProjectInvitation.objects.get(pk=invitation_id)
        invitation.resent_at = timezone.now()
        invitation.save()
        project_activation_url = get_project_invitation_url(self.context["request"])
        send_project_invitation_email_async.delay(invitation_id, project_activation_url)
