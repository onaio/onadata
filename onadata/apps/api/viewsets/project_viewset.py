# -*- coding: utf-8 -*-
"""
The /projects API endpoint implementation.
"""
from django.core.cache import cache
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from onadata.apps.api import tools as utils
from onadata.apps.api.permissions import ProjectPermissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models import Project, XForm
from onadata.apps.main.models import UserProfile
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.data import strtobool
from onadata.libs.filters import AnonUserProjectFilter, ProjectOwnerFilter, TagFilter
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.labels_mixin import LabelsMixin
from onadata.libs.mixins.profiler_mixin import ProfilerMixin
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.serializers.project_serializer import (
    BaseProjectSerializer,
    ProjectSerializer,
)
from onadata.libs.serializers.share_project_serializer import (
    RemoveUserFromProjectSerializer,
    ShareProjectSerializer,
)
from onadata.libs.serializers.user_profile_serializer import UserProfileSerializer
from onadata.libs.serializers.xform_serializer import (
    XFormCreateSerializer,
    XFormSerializer,
)
from onadata.libs.utils.cache_tools import PROJ_OWNER_CACHE, safe_delete
from onadata.libs.utils.common_tools import merge_dicts
from onadata.libs.utils.export_tools import str_to_bool
from onadata.settings.common import DEFAULT_FROM_EMAIL, SHARE_PROJECT_SUBJECT

# pylint: disable=invalid-name
BaseViewset = get_baseviewset_class()


# pylint: disable=too-many-ancestors
class ProjectViewSet(
    AuthenticateHeaderMixin,
    CacheControlMixin,
    ETagsMixin,
    LabelsMixin,
    ProfilerMixin,
    BaseViewset,
    ModelViewSet,
):

    """
    List, Retrieve, Update, Create Project and Project Forms.
    """

    # pylint: disable=no-member
    queryset = Project.objects.filter(deleted_at__isnull=True).select_related()
    serializer_class = ProjectSerializer
    lookup_field = "pk"
    extra_lookup_fields = None
    permission_classes = [ProjectPermissions]
    filter_backends = (AnonUserProjectFilter, ProjectOwnerFilter, TagFilter)
    pagination_class = StandardPageNumberPagination

    def get_serializer_class(self):
        """Return BaseProjectSerializer class when listing projects."""
        if self.action == "list":
            return BaseProjectSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        """Use 'prepared' prefetched queryset for GET requests."""
        if self.request.method.upper() in ["GET", "OPTIONS"]:
            self.queryset = Project.prefetched.filter(
                deleted_at__isnull=True, organization__is_active=True
            )

        return super().get_queryset()

    def update(self, request, *args, **kwargs):
        """Updates project properties and set's cache with the updated records."""
        project_id = kwargs.get("pk")
        response = super().update(request, *args, **kwargs)
        cache.set(f"{PROJ_OWNER_CACHE}{project_id}", response.data)
        return response

    def retrieve(self, request, *args, **kwargs):
        """Retrieve single project"""
        project_id = kwargs.get("pk")
        project = cache.get(f"{PROJ_OWNER_CACHE}{project_id}")
        if project:
            return Response(project)
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        serializer = ProjectSerializer(self.object, context={"request": request})
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        """Returns a list of projects"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page:
            serializer = self.get_serializer(page, many=True)
        else:
            serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data)

    @action(methods=["POST", "GET"], detail=True)
    def forms(self, request, **kwargs):
        """Add a form to a project or list forms for the project.

        The request key `xls_file` holds the XLSForm file object.
        """
        # pylint: disable=attribute-defined-outside-init
        project = self.object = self.get_object()
        if request.method.upper() == "POST":
            survey = utils.publish_project_xform(request, project)

            if isinstance(survey, XForm):
                if "formid" in request.data:
                    serializer_cls = XFormSerializer
                else:
                    serializer_cls = XFormCreateSerializer

                serializer = serializer_cls(survey, context={"request": request})

                published_by_formbuilder = request.data.get("published_by_formbuilder")

                if str_to_bool(published_by_formbuilder):
                    MetaData.published_by_formbuilder(survey, "True")

                return Response(serializer.data, status=status.HTTP_201_CREATED)

            return Response(survey, status=status.HTTP_400_BAD_REQUEST)

        xforms = XForm.objects.filter(project=project)
        serializer = XFormSerializer(xforms, context={"request": request}, many=True)

        return Response(serializer.data)

    @action(methods=["PUT"], detail=True)
    def share(self, request, *args, **kwargs):
        """
        Allow sharing of a project to a user.
        """
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        data = merge_dicts(request.data.dict(), {"project": self.object.pk})

        remove = data.get("remove")
        if remove and remove is not isinstance(remove, bool):
            remove = strtobool(remove)

        if remove:
            serializer = RemoveUserFromProjectSerializer(data=data)
        else:
            serializer = ShareProjectSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            email_msg = data.get("email_msg")
            if email_msg:
                # send out email message.
                try:
                    user = serializer.instance.user
                except AttributeError:
                    for instance in serializer.instance:
                        user = instance.user
                        send_mail(
                            SHARE_PROJECT_SUBJECT.format(self.object.name),
                            email_msg,
                            DEFAULT_FROM_EMAIL,
                            (user.email,),
                        )
                else:
                    send_mail(
                        SHARE_PROJECT_SUBJECT.format(self.object.name),
                        email_msg,
                        DEFAULT_FROM_EMAIL,
                        (user.email,),
                    )
        else:
            return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # clear cache
        safe_delete(f"{PROJ_OWNER_CACHE}{self.object.pk}")

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["DELETE", "GET", "POST"], detail=True)
    def star(self, request, *args, **kwargs):
        """
        Allows to add a user that stars a project.
        """
        user = request.user
        # pylint: disable=attribute-defined-outside-init
        self.object = project = get_object_or_404(Project, pk=kwargs.get("pk"))

        if request.method == "DELETE":
            project.user_stars.remove(user)
            project.save()
        elif request.method == "POST":
            project.user_stars.add(user)
            project.save()
        elif request.method == "GET":
            users = project.user_stars.values("pk")
            user_profiles = UserProfile.objects.filter(user__in=users)
            serializer = UserProfileSerializer(
                user_profiles, context={"request": request}, many=True
            )

            return Response(serializer.data)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def destroy(self, request, *args, **kwargs):
        """ "Soft deletes a project"""
        project = self.get_object()
        user = request.user
        project.soft_delete(user)

        return Response(status=status.HTTP_204_NO_CONTENT)
