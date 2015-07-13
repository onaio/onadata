from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from rest_framework import filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import DjangoObjectPermissions

from onadata.libs.filters import TeamOrgFilter
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
from onadata.libs.serializers.team_serializer import TeamSerializer
from onadata.libs.serializers.share_team_project_serializer import (
    ShareTeamProjectSerializer, RemoveTeamFromProjectSerializer)
from onadata.apps.api.models import Team
from onadata.apps.api.tools import add_user_to_team, remove_user_from_team


class TeamViewSet(CacheControlMixin, LastModifiedMixin, ModelViewSet):
    """
    This endpoint allows you to create, update and view team information.
    """
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    lookup_field = 'pk'
    extra_lookup_fields = None
    permission_classes = [DjangoObjectPermissions]
    filter_backends = (filters.DjangoObjectPermissionsFilter,
                       TeamOrgFilter)

    @action(methods=['DELETE', 'GET', 'POST'])
    def members(self, request, *args, **kwargs):
        team = self.get_object()
        data = {}
        status_code = status.HTTP_200_OK

        if request.method in ['DELETE', 'POST']:
            username = request.DATA.get('username') or\
                request.QUERY_PARAMS.get('username')

            if username:
                try:
                    user = User.objects.get(username__iexact=username)
                except User.DoesNotExist:
                    status_code = status.HTTP_400_BAD_REQUEST
                    data['username'] = [
                        _(u"User `%(username)s` does not exist."
                          % {'username': username})]
                else:
                    if request.method == 'POST':
                        add_user_to_team(team, user)
                    elif request.method == 'DELETE':
                        remove_user_from_team(team, user)
                    status_code = status.HTTP_201_CREATED
            else:
                status_code = status.HTTP_400_BAD_REQUEST
                data['username'] = [_(u"This field is required.")]

        if status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            data = [u.username for u in team.user_set.all()]

        return Response(data, status=status_code)

    @action(methods=['POST'])
    def share(self, request, *args, **kwargs):
        self.object = self.get_object()
        data = dict(request.DATA.items() + [('team', self.object.pk)])

        if data.get("remove"):
            serializer = RemoveTeamFromProjectSerializer(data=data)
        else:
            serializer = ShareTeamProjectSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
        else:
            return Response(data=serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)
