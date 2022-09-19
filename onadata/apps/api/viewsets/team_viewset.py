# -*- coding: utf-8 -*-
"""
The /teams API endpoint implementation.
"""
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import DjangoObjectPermissions
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework_guardian.filters import ObjectPermissionsFilter

from onadata.apps.api.models import Team
from onadata.apps.api.tools import (
    add_user_to_team,
    get_baseviewset_class,
    remove_user_from_team,
)
from onadata.libs.data import strtobool
from onadata.libs.filters import TeamOrgFilter
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.serializers.share_team_project_serializer import (
    RemoveTeamFromProjectSerializer,
    ShareTeamProjectSerializer,
)
from onadata.libs.serializers.team_serializer import TeamSerializer
from onadata.libs.utils.common_tools import merge_dicts

# pylint: disable=invalid-name
BaseViewset = get_baseviewset_class()
# pylint: disable=invalid-name
User = get_user_model()


# pylint: disable=too-many-ancestors
class TeamViewSet(
    AuthenticateHeaderMixin, CacheControlMixin, ETagsMixin, BaseViewset, ModelViewSet
):
    """
    This endpoint allows you to create, update and view team information.
    """

    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    lookup_field = "pk"
    extra_lookup_fields = None
    permission_classes = [DjangoObjectPermissions]
    filter_backends = (ObjectPermissionsFilter, TeamOrgFilter)

    @action(methods=["DELETE", "GET", "POST"], detail=True)
    def members(self, request, *args, **kwargs):
        """
        Returns members of an organization.
        """
        team = self.get_object()
        data = {}
        status_code = status.HTTP_200_OK

        if request.method in ["DELETE", "POST"]:
            username = request.data.get("username") or request.query_params.get(
                "username"
            )

            if username:
                try:
                    user = User.objects.get(username__iexact=username)
                except User.DoesNotExist:
                    status_code = status.HTTP_400_BAD_REQUEST
                    data["username"] = [_(f"User `{username}` does not exist.")]
                else:
                    if request.method == "POST":
                        add_user_to_team(team, user)
                    elif request.method == "DELETE":
                        remove_user_from_team(team, user)
                    status_code = status.HTTP_201_CREATED
            else:
                status_code = status.HTTP_400_BAD_REQUEST
                data["username"] = [_("This field is required.")]

        if status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            data = [u.username for u in team.user_set.all()]

        return Response(data, status=status_code)

    @action(methods=["POST"], detail=True)
    def share(self, request, *args, **kwargs):
        """
        Performs sharing a team project operations.
        """
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        data = merge_dicts(request.data.items(), {"team": self.object.pk})

        remove = data.get("remove")
        if remove and remove is not isinstance(remove, bool):
            remove = strtobool(remove)

        if remove:
            serializer = RemoveTeamFromProjectSerializer(data=data)
        else:
            serializer = ShareTeamProjectSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
        else:
            return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)
