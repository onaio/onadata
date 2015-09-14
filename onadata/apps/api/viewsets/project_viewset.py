from django.shortcuts import get_object_or_404
from django.core.mail import send_mail

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from onadata.libs.filters import (
    AnonUserProjectFilter,
    ProjectOwnerFilter,
    TagFilter)
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.labels_mixin import LabelsMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.serializers.user_profile_serializer import\
    UserProfileSerializer
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs.serializers.share_project_serializer import\
    ShareProjectSerializer, RemoveUserFromProjectSerializer
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.apps.api import tools as utils
from onadata.apps.api.permissions import ProjectPermissions
from onadata.apps.logger.models import Project
from onadata.apps.logger.models import XForm
from onadata.apps.main.models import UserProfile
from onadata.settings.common import (
    DEFAULT_FROM_EMAIL,
    SHARE_PROJECT_SUBJECT)
from onadata.apps.api.models import Team
from onadata.libs.permissions import OwnerRole, ReadOnlyRole
from onadata.apps.api.tools import get_baseviewset_class


BaseViewset = get_baseviewset_class()


class ProjectViewSet(AuthenticateHeaderMixin,
                     CacheControlMixin,
                     ETagsMixin, LabelsMixin, BaseViewset, ModelViewSet):
    """
    List, Retrieve, Update, Create Project and Project Forms.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    lookup_field = 'pk'
    extra_lookup_fields = None
    permission_classes = [ProjectPermissions]
    filter_backends = (AnonUserProjectFilter,
                       ProjectOwnerFilter,
                       TagFilter)

    @action(methods=['POST', 'GET'])
    def forms(self, request, **kwargs):
        """Add a form to a project or list forms for the project.

        The request key `xls_file` holds the XLSForm file object.
        """
        project = self.object = self.get_object()
        if request.method.upper() == 'POST':
            survey = utils.publish_project_xform(request, project)

            if isinstance(survey, XForm):
                xform = XForm.objects.get(pk=survey.pk)
                serializer = XFormSerializer(
                    xform, context={'request': request})

                return Response(serializer.data,
                                status=status.HTTP_201_CREATED)

            return Response(survey, status=status.HTTP_400_BAD_REQUEST)

        xforms = XForm.objects.filter(project=project)
        serializer = XFormSerializer(xforms, context={'request': request},
                                     many=True)

        return Response(serializer.data)

    @action(methods=['PUT'])
    def share(self, request, *args, **kwargs):
        self.object = self.get_object()
        data = dict(request.DATA.items() + [('project', self.object.pk)])
        if data.get("remove"):
            serializer = RemoveUserFromProjectSerializer(data=data)
        else:
            serializer = ShareProjectSerializer(data=data)

        if serializer.is_valid():
            serializer.save()

            email_msg = data.get('email_msg')

            if email_msg:
                # send out email message.
                user = serializer.object.user
                send_mail(SHARE_PROJECT_SUBJECT.format(self.object.name),
                          email_msg,
                          DEFAULT_FROM_EMAIL,
                          (user.email, ))

        else:
            return Response(data=serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=['DELETE', 'GET', 'POST'])
    def star(self, request, *args, **kwargs):
        user = request.user
        self.object = project = get_object_or_404(Project,
                                                  pk=kwargs.get('pk'))

        if request.method == 'DELETE':
            project.user_stars.remove(user)
            project.save()
        elif request.method == 'POST':
            project.user_stars.add(user)
            project.save()
        elif request.method == 'GET':
            users = project.user_stars.values('pk')
            user_profiles = UserProfile.objects.filter(user__in=users)
            serializer = UserProfileSerializer(user_profiles,
                                               context={'request': request},
                                               many=True)

            return Response(serializer.data)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def list(self, request, *args, **kwargs):

        owner = request.QUERY_PARAMS.get('owner')

        if owner:
            kwargs = {'organization__username__iexact': owner}
            self.object_list = self.filter_queryset(self.get_queryset()) | \
                Project.objects.filter(shared=True, **kwargs)
        else:
            self.object_list = self.filter_queryset(self.get_queryset())

        serializer = self.get_serializer(self.object_list, many=True)

        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        owner_url = request.DATA.get('owner').split('/')
        owner = owner_url[len(owner_url) - 1]

        teams = Team.objects.filter(organization__username=owner)
        project = self.get_object()
        for a in teams:
            if a.name.split("#")[1] == 'Owners':
                OwnerRole.add(a, project)
            elif a.name.split("#")[1] == 'members':
                ReadOnlyRole.add(a, project)
        return super(ProjectViewSet, self).partial_update(
            request, *args, **kwargs)
