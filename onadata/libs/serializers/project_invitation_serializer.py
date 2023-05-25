import re
from rest_framework import serializers
from onadata.apps.logger.models import ProjectInvitation
from onadata.libs.permissions import ROLES
from django.conf import settings
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class ProjectInvitationSerializer(serializers.ModelSerializer):
    """Serializer for ProjectInvitation model object"""

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

        # email should not be of an existing user
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(_("User already exists"))

        return email

    def validate_role(self, role):
        """Validate `role` field"""
        if role not in ROLES:
            raise serializers.ValidationError(_("Invalid role."))

        return role

    def get_unique_together_validators(self):
        """Overriding method to disable unique together checks"""
        return []

    class Meta:
        model = ProjectInvitation
        fields = (
            "id",
            "email",
            "project",
            "role",
            "status",
        )


class ProjectInvitationUpdateBaseSerializer(serializers.Serializer):
    """Base serializer for project invitation updates"""

    invitation_id = serializers.IntegerField()

    def validate_invitation_id(self, invitation_id):
        """Validate `invitation_id` field"""
        try:
            ProjectInvitation.objects.get(pk=invitation_id)

        except ProjectInvitation.DoesNotExist:
            raise serializers.ValidationError(_("Invalid invitation_id."))

        return invitation_id


class ProjectInvitationRevokeSerializer(ProjectInvitationUpdateBaseSerializer):
    """Serializer for revoking a project invitation"""

    def validate_invitation_id(self, invitation_id):
        super().validate_invitation_id(invitation_id)

        invitation = ProjectInvitation.objects.get(pk=invitation_id)

        if invitation.status != ProjectInvitation.Status.PENDING:
            raise serializers.ValidationError(
                _(
                    "This is not a pending invitation. You only revoke a pending invitation"
                )
            )

        return invitation_id

    def save(self, **kwargs):
        invitation_id = self.validated_data.get("invitation_id")
        invitation = ProjectInvitation.objects.get(pk=invitation_id)
        invitation.status = ProjectInvitation.Status.REVOKED
        invitation.save()


class ProjectInvitationResendSerializer(ProjectInvitationUpdateBaseSerializer):
    """Serializer for resending a project invitation"""

    def validate_invitation_id(self, invitation_id):
        super().validate_invitation_id(invitation_id)

        invitation = ProjectInvitation.objects.get(pk=invitation_id)

        if invitation.status != ProjectInvitation.Status.PENDING:
            raise serializers.ValidationError(
                _(
                    "This is not a pending invitation. You only resend a pending invitation"
                )
            )

        return invitation_id

    def save(self, **kwargs):
        invitation_id = self.validated_data.get("invitation_id")
        invitation = ProjectInvitation.objects.get(pk=invitation_id)
        invitation.resent_at = timezone.now()
        invitation.save()
