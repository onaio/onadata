"""
Project serializer for v2 API
"""

from django.conf import settings
from django.contrib.auth import get_user_model

from guardian.shortcuts import get_perms
from rest_framework import serializers

from onadata.apps.logger.models.project import Project
from onadata.libs.permissions import get_role
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.serializers.project_serializer import PROJECT_PUBLIC_EXCLUDED_FIELDS
from onadata.libs.serializers.project_serializer import (
    ProjectSerializer as ProjectSerializerV1,
)
from onadata.libs.serializers.project_serializer import (
    PublicProjectFieldsMixin,
    get_last_submission_date,
    get_num_datasets,
    is_starred,
)
from onadata.libs.serializers.tag_list_serializer import TagListSerializer

# pylint: disable=invalid-name
User = get_user_model()


def get_current_user_role(project, request):
    """Return the role of the request user in the project."""
    if request.user.is_anonymous:
        return None

    perms = get_perms(request.user, project)

    return get_role(perms, project)


class ProjectListSerializer(
    PublicProjectFieldsMixin, serializers.HyperlinkedModelSerializer
):
    """Serializer for a list of Projects"""

    projectid = serializers.ReadOnlyField(source="id")
    url = serializers.HyperlinkedIdentityField(
        view_name="project-v2-detail", lookup_field="pk"
    )
    owner = serializers.HyperlinkedRelatedField(
        view_name="user-detail",
        source="organization",
        lookup_field="username",
        queryset=User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
        ),
    )
    metadata = JsonField(required=False)
    starred = serializers.SerializerMethodField()
    public = serializers.BooleanField(source="shared")
    tags = TagListSerializer(read_only=True)
    num_datasets = serializers.SerializerMethodField()
    last_submission_date = serializers.SerializerMethodField()
    current_user_role = serializers.SerializerMethodField()
    public_excluded_fields = PROJECT_PUBLIC_EXCLUDED_FIELDS | {"current_user_role"}

    class Meta:
        model = Project
        fields = [
            "url",
            "projectid",
            "name",
            "owner",
            "metadata",
            "starred",
            "public",
            "tags",
            "num_datasets",
            "current_user_role",
            "last_submission_date",
            "date_created",
            "date_modified",
        ]

    def get_starred(self, obj):
        """
        Return True if request user has starred this project.
        """
        return is_starred(obj, self.context["request"])

    def get_current_user_role(self, obj):
        """
        Return the role of the request user in the project.
        """
        return get_current_user_role(obj, self.context["request"])

    def get_num_datasets(self, obj):
        """
        Return the number of datasets attached to the project.
        """
        return get_num_datasets(obj)

    def get_last_submission_date(self, obj):
        """
        Return the most recent submission date to any of the projects datasets.
        """
        return get_last_submission_date(obj)


class ProjectPrivateSerializer(serializers.ModelSerializer):
    """User specific fields for a Project"""

    current_user_role = serializers.SerializerMethodField()
    starred = serializers.SerializerMethodField()

    def get_current_user_role(self, obj):
        """Return the role of the request user in the project."""
        return get_current_user_role(obj, self.context["request"])

    def get_starred(self, obj):
        """Return True if request user has starred this project."""
        return is_starred(obj, self.context["request"])

    class Meta:
        model = Project
        fields = ("current_user_role", "starred")


class ProjectSerializer(ProjectSerializerV1):
    """Serializer for a Project"""

    url = serializers.HyperlinkedIdentityField(
        view_name="project-v2-detail", lookup_field="pk"
    )

    class Meta(ProjectSerializerV1.Meta):
        fields = [
            "url",
            "projectid",
            "name",
            "owner",
            "created_by",
            "metadata",
            "starred",
            "forms",
            "public",
            "tags",
            "num_datasets",
            "last_submission_date",
            "data_views",
            "date_created",
            "date_modified",
        ]
