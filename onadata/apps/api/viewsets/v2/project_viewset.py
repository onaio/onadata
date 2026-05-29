"""
Project viewset for v2 API
"""

from rest_framework.decorators import action
from rest_framework.response import Response

from onadata.apps.api.viewsets.project_viewset import ProjectViewSet as ProjectViewSetV1
from onadata.libs.serializers.project_serializer import get_teams, get_users
from onadata.libs.serializers.v2.project_serializer import (
    ProjectListSerializer,
    ProjectPrivateSerializer,
    ProjectSerializer,
)
from onadata.libs.utils.cache_tools import (
    PROJ_OWNER_CACHE,
    safe_cache_get,
    safe_cache_set,
)


# pylint: disable=too-many-ancestors
class ProjectViewSet(ProjectViewSetV1):
    """List, Retrieve, Update, Create Project and Project Forms."""

    serializer_class = ProjectSerializer

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
        base_data = safe_cache_get(f"{PROJ_OWNER_CACHE}{project.pk}")

        if base_data is None:
            base_data = ProjectSerializer(project, context={"request": request}).data

        # Cache data
        safe_cache_set(f"{PROJ_OWNER_CACHE}{project.pk}", base_data)

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
