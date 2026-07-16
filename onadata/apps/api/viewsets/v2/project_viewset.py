"""
Project viewset for v2 API
"""

from django.db.models import Max, Q

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from onadata.apps.api.viewsets.project_viewset import ProjectViewSet as ProjectViewSetV1
from onadata.libs.filters import (
    AnonUserProjectFilter,
    ProjectOwnerFilter,
    ProjectRoleFilter,
    ProjectStarredFilter,
    TagFilter,
)
from onadata.libs.serializers.project_serializer import get_teams, get_users
from onadata.libs.serializers.v2.project_serializer import (
    ProjectListSerializer,
    ProjectPrivateSerializer,
    ProjectSerializer,
)
from onadata.libs.utils.cache_tools import (
    get_project_cache_key,
    get_shared_project_detail_cache_data,
    is_public_project_access,
    safe_cache_get,
    safe_cache_set,
)


# pylint: disable=too-many-ancestors
class ProjectViewSet(ProjectViewSetV1):
    """List, Retrieve, Update, Create Project and Project Forms."""

    serializer_class = ProjectSerializer
    api_version = "v2"

    filter_backends = (
        AnonUserProjectFilter,
        ProjectOwnerFilter,
        TagFilter,
        DjangoFilterBackend,
        ProjectStarredFilter,
        ProjectRoleFilter,
        SearchFilter,
        OrderingFilter,
    )
    filterset_fields = ("shared",)
    search_fields = ["name", "organization__username"]
    ordering_fields = [
        "name",
        "date_created",
        "last_submission_date",
        "metadata__category",
    ]

    def get_queryset(self):
        """Annotate `last_submission_date` only when it is requested for ordering.

        Overrides super().get_queryset()
        """
        queryset = super().get_queryset()
        ordering = self.request.query_params.get("ordering", "")
        requested = {field.strip().removeprefix("-") for field in ordering.split(",")}
        if "last_submission_date" in requested:
            # Annotation is only for ordering; the serializer still computes
            # last_submission_date itself. Exclude soft-deleted forms.
            queryset = queryset.annotate(
                last_submission_date=Max(
                    "xform__last_submission_time",
                    filter=Q(xform__deleted_at__isnull=True),
                )
            )
        return queryset

    def get_serializer_class(self):
        """Get serializer class based on action

        Overrides super().get_serializer_class()
        """
        if self.action == "list":
            return ProjectListSerializer

        return super().get_serializer_class()

    def retrieve(self, request, *args, **kwargs):
        """Retrive a single Project

        Overrides super().retrieve()
        """
        project = self.get_object()
        cache_key = get_project_cache_key(
            project.pk, request, project, api_version=self.api_version
        )
        base_data = safe_cache_get(cache_key)

        if base_data is None:
            serializer = ProjectSerializer(project, context={"request": request})
            base_data = get_shared_project_detail_cache_data(serializer.data)
            safe_cache_set(cache_key, base_data)
        else:
            base_data = get_shared_project_detail_cache_data(base_data)

        if is_public_project_access(request, project):
            # Public shape omits user-specific fields such as starred
            return Response(base_data)

        # Inject user specific fields
        private_data = ProjectPrivateSerializer(
            project, context={"request": request}
        ).data

        return Response({**base_data, **private_data})

    @action(methods=["GET"], detail=True)
    def users(self, request, *args, **kwargs):
        """Return the users and organizations that have access to the project.

        Accessible to any member of the project.
        """
        project = self.get_object()
        # No need for view level caching
        # get_users caches the result under PROJ_PERM_CACHE
        # (ps-project_permissions-<pk>) and is invalidated whenever a member is
        # added, removed, or has their role changed (ShareProject.save in
        # onadata/libs/models/share_project.py).
        data = get_users(project, {"request": request})

        return Response(data)

    @action(methods=["GET"], detail=True)
    def teams(self, request, *args, **kwargs):
        """Return the teams that have access to the project.

        Accessible to any member of the project.
        """
        project = self.get_object()
        # No need for view level caching
        # get_teams caches the result under PROJ_TEAM_USERS_CACHE
        # (ps-project-team-users<pk>).
        data = get_teams(project)

        return Response(data)
