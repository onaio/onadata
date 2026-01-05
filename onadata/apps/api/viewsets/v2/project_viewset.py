"""
Project viewset for v2 API
"""

from rest_framework.response import Response

from onadata.apps.api.viewsets.project_viewset import ProjectViewSet as ProjectViewSetV1
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs.serializers.v2.project_serializer import (
    ProjectListSerializer,
    ProjectPrivateSerializer,
)
from onadata.libs.utils.cache_tools import (
    PROJ_OWNER_CACHE,
    safe_cache_get,
    safe_cache_set,
)


# pylint: disable=too-many-ancestors
class ProjectViewSet(ProjectViewSetV1):
    """List, Retrieve, Update, Create Project and Project Forms."""

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
        public_data = safe_cache_get(f"{PROJ_OWNER_CACHE}{project.pk}")

        if not public_data:
            public_data = ProjectSerializer(project, context={"request": request}).data

        # Cache data
        safe_cache_set(f"{PROJ_OWNER_CACHE}{project.pk}", public_data)

        # Inject user specific fields
        private_data = ProjectPrivateSerializer(
            project, context={"request": request}
        ).data

        return Response({**public_data, **private_data})
