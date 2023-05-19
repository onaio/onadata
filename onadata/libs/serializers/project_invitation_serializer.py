from rest_framework import serializers
from onadata.apps.logger.models import ProjectInvitation


class ProjectInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectInvitation
        fields = (
            "id",
            "email",
            "project",
            "role",
            "status",
        )
