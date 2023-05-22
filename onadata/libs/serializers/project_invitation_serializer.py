import re
from rest_framework import serializers
from onadata.apps.logger.models import ProjectInvitation
from django.conf import settings
from django.utils.translation import gettext as _


class ProjectInvitationSerializer(serializers.ModelSerializer):
    def validate_email(self, email):
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

    class Meta:
        model = ProjectInvitation
        fields = (
            "id",
            "email",
            "project",
            "role",
            "status",
        )
