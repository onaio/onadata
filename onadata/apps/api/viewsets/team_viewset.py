# -*- coding: utf-8 -*-
"""
The /teams API endpoint implementation.
"""
from itertools import chain

from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from guardian.shortcuts import get_perms
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import DjangoObjectPermissions
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework_guardian.filters import ObjectPermissionsFilter

from onadata.apps.api.models import OrganizationProfile, Team
from onadata.apps.api.models.organization_profile import is_organization_owners_team
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
from onadata.libs.permissions import ROLES, is_organization_admin
from onadata.libs.serializers.share_team_project_serializer import (
    RemoveTeamFromProjectSerializer,
    ShareTeamProjectSerializer,
)
from onadata.libs.serializers.team_serializer import TeamSerializer
from onadata.libs.stepup import RequiresStepUp
from onadata.libs.stepup.gate import changed_gated_actions
from onadata.libs.stepup.policy import (
    GATE_GRANT_ORG_ADMIN,
    GATE_SHARE_TEAM_ADMIN,
    is_gated,
)
from onadata.libs.stepup.sharing import (
    grants_admin_role,
    reapplying_appoints_admins,
    team_reaches_admin_role,
)
from onadata.libs.utils.common_tools import merge_dicts

# pylint: disable=invalid-name
BaseViewset = get_baseviewset_class()
# pylint: disable=invalid-name
User = get_user_model()


def _team_holds_role(team, project, role):
    """Whether sharing ``project`` with ``team`` as ``role`` would grant
    nothing new. A share also applies the role to every form in the project,
    so the forms are checked as well."""
    return all(
        role.has_role(get_perms(team, obj), obj)
        for obj in chain([project], project.xform_set.all())
    )


# pylint: disable=too-many-ancestors
class TeamViewSet(
    AuthenticateHeaderMixin,
    CacheControlMixin,
    ETagsMixin,
    RequiresStepUp,
    BaseViewset,
    ModelViewSet,
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

    def _check_organization_admin(self, request, team):
        """Rejects requesters who do not administer the team's organization."""
        organization = OrganizationProfile.objects.get(user=team.organization)

        if not is_organization_admin(request.user, organization):
            raise PermissionDenied(
                _("You must be an owner or manager of the organization.")
            )

    def _join_refusal(self, request, team, user):
        """Joining a team hands the new member every role the team holds.
        Joining the Owners team makes someone an organisation owner. Joining
        any team that owns or manages a project or form makes them an admin
        of it.

        The Owners team is both, and one grant covers it, under the first
        audience the deployment gates."""
        if request.method != "POST" or team.user_set.filter(pk=user.pk).exists():
            return None
        gated = changed_gated_actions(
            (
                (GATE_GRANT_ORG_ADMIN, is_organization_owners_team(team)),
                (GATE_SHARE_TEAM_ADMIN, lambda: team_reaches_admin_role(team)),
            )
        )
        return self.check_step_up(request, gated[0]) if gated else None

    def _share_admin_refusal(self, request, validated_data):
        """Refuse giving a team an owner or manager role without a grant.

        The role may be named outright or reached on a form through its meta
        permissions."""
        if not is_gated(GATE_SHARE_TEAM_ADMIN):
            return None
        role_name = validated_data["role"]
        team, project = validated_data["team"], validated_data["project"]
        xforms = project.xform_set.all()
        grants_new_admin = grants_admin_role(
            xforms, role_name
        ) and not _team_holds_role(team, project, ROLES[role_name])
        # A share re-applies each form's meta permissions to all its users,
        # whatever role it names.
        if grants_new_admin or reapplying_appoints_admins(xforms):
            return self.check_step_up(request, GATE_SHARE_TEAM_ADMIN)
        return None

    def destroy(self, request, *args, **kwargs):
        """Deletes a team."""
        self._check_organization_admin(request, self.get_object())

        return super().destroy(request, *args, **kwargs)

    @action(methods=["DELETE", "GET", "POST"], detail=True)
    def members(self, request, *args, **kwargs):
        """
        Returns members of an organization.
        """
        team = self.get_object()
        data = {}
        status_code = status.HTTP_200_OK

        if request.method in ["DELETE", "POST"]:
            self._check_organization_admin(request, team)

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
                    refusal = self._join_refusal(request, team, user)
                    if refusal is not None:
                        return refusal
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

        context = {"request": request}
        if remove:
            serializer = RemoveTeamFromProjectSerializer(data=data, context=context)
        else:
            serializer = ShareTeamProjectSerializer(data=data, context=context)

        if not serializer.is_valid():
            return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        refusal = (
            None
            if remove
            else self._share_admin_refusal(request, serializer.validated_data)
        )
        if refusal is not None:
            return refusal
        serializer.save()

        return Response(status=status.HTTP_204_NO_CONTENT)
