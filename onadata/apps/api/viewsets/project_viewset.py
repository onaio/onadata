# -*- coding: utf-8 -*-
"""
The /projects API endpoint implementation.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from reversion.views import RevisionMixin

from onadata.apps.api import tools as utils
from onadata.apps.api.permissions import ProjectPermissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models import Project, ProjectInvitation, XForm
from onadata.apps.main.models import UserProfile
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.data import strtobool
from onadata.libs.filters import (
    ActiveProjectOrganizationFilter,
    AnonUserProjectFilter,
    ProjectOwnerFilter,
    TagFilter,
)
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.labels_mixin import LabelsMixin
from onadata.libs.mixins.profiler_mixin import ProfilerMixin
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.permissions import ROLES
from onadata.libs.serializers.project_invitation_serializer import (
    ProjectInvitationResendSerializer,
    ProjectInvitationRevokeSerializer,
    ProjectInvitationSerializer,
)
from onadata.libs.serializers.project_serializer import (
    BaseProjectSerializer,
    ProjectSerializer,
    is_starred,
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
from onadata.libs.stepup import RequiresStepUp
from onadata.libs.stepup.drf import gated_change_refusal
from onadata.libs.stepup.policy import (
    ADMIN_ROLE_NAMES,
    GATE_INVITE_PROJECT_ADMIN,
    GATE_PUBLISH_DATA,
    GATE_SHARE_PROJECT_ADMIN,
    GATE_TRANSFER_PROJECT,
)
from onadata.libs.utils.cache_tools import (
    clear_project_owner_cache,
    get_project_cache_key,
    get_shared_project_detail_cache_data,
    safe_cache_get,
    safe_cache_set,
)
from onadata.libs.utils.common_tools import merge_dicts, report_exception
from onadata.libs.utils.export_tools import str_to_bool
from onadata.libs.utils.project_utils import propagate_project_permissions_async
from onadata.settings.common import DEFAULT_FROM_EMAIL, SHARE_PROJECT_SUBJECT

logger = logging.getLogger(__name__)

# pylint: disable=invalid-name
BaseViewset = get_baseviewset_class()
User = get_user_model()


def _publishes_data(project, validated_data):
    """Saving a public project makes every private form in it public, data
    included, whether or not ``public`` is what changed."""
    if not validated_data.get("shared", project.shared):
        return False
    return not project.shared or project.xform_set.filter(shared=False).exists()


def _transfers(project, validated_data):
    new_owner = validated_data.get("organization", project.organization)
    return new_owner != project.organization


# pylint: disable=too-many-ancestors
class ProjectViewSet(
    AuthenticateHeaderMixin,
    CacheControlMixin,
    ETagsMixin,
    LabelsMixin,
    ProfilerMixin,
    RevisionMixin,
    RequiresStepUp,
    BaseViewset,
    ModelViewSet,
):
    """
    List, Retrieve, Update, Create Project and Project Forms.
    """

    # pylint: disable=no-member
    queryset = (
        Project.objects.filter(deleted_at__isnull=True, organization__is_active=True)
        .order_by("-date_created")
        .select_related()
    )
    serializer_class = ProjectSerializer
    lookup_field = "pk"
    extra_lookup_fields = None
    permission_classes = [ProjectPermissions]
    filter_backends = (
        AnonUserProjectFilter,
        ProjectOwnerFilter,
        TagFilter,
        ActiveProjectOrganizationFilter,
    )
    pagination_class = StandardPageNumberPagination
    api_version = "v1"

    def get_serializer_class(self):
        """Override `get_serializer_class."""
        if self.action == "list":
            return BaseProjectSerializer

        if self.action == "invitations":
            return ProjectInvitationSerializer

        if self.action == "revoke_invitation":
            return ProjectInvitationRevokeSerializer

        if self.action == "resend_invitation":
            return ProjectInvitationResendSerializer

        return super().get_serializer_class()

    def get_queryset(self):
        """Use the active-organization prefetched queryset."""
        if self.request.method.upper() in ["GET", "OPTIONS"]:
            self.queryset = Project.prefetched.filter(
                deleted_at__isnull=True, organization__is_active=True
            ).order_by("-date_created")

        return super().get_queryset()

    def _update_refusal(self, request, project, validated_data):
        """Refuse whichever gated change saving ``validated_data`` would make,
        or None."""
        return gated_change_refusal(
            self,
            request,
            (
                (GATE_TRANSFER_PROJECT, _transfers(project, validated_data)),
                (GATE_PUBLISH_DATA, _publishes_data(project, validated_data)),
            ),
        )

    def _move_form_refusal(self, request, project, xform):
        """A form that is neither public nor has public data takes on a public
        project's visibility when moved into it."""
        if project.shared and not (xform.shared or xform.shared_data):
            return self.check_step_up(request, GATE_PUBLISH_DATA)
        return None

    def update(self, request, *args, **kwargs):
        """Updates project properties and set's cache with the updated records."""
        project_id = kwargs.get("pk")
        project = self.get_object()
        serializer = self.get_serializer(
            project, data=request.data, partial=kwargs.pop("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        refusal = self._update_refusal(request, project, serializer.validated_data)
        if refusal is not None:
            return refusal
        self.perform_update(serializer)
        response = Response(serializer.data)
        clear_project_owner_cache(project_id)
        safe_cache_set(
            get_project_cache_key(project_id, request, api_version=self.api_version),
            get_shared_project_detail_cache_data(response.data),
        )
        return response

    def retrieve(self, request, *args, **kwargs):
        """Retrieve single project"""
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        cache_key = get_project_cache_key(self.object.pk, request, self.object)
        project_data = safe_cache_get(cache_key)

        if project_data is None:
            serializer = ProjectSerializer(self.object, context={"request": request})
            project_data = get_shared_project_detail_cache_data(serializer.data)
            safe_cache_set(cache_key, project_data)
        else:
            project_data = get_shared_project_detail_cache_data(project_data)

        return Response({**project_data, "starred": is_starred(self.object, request)})

    @action(methods=["POST", "GET"], detail=True)
    def forms(self, request, **kwargs):
        """Add a form to a project or list forms for the project.

        The request key `xls_file` holds the XLSForm file object.
        """
        # pylint: disable=attribute-defined-outside-init
        project = self.object = self.get_object()
        if request.method.upper() == "POST":
            survey = utils.publish_project_xform(
                request,
                project,
                move_refusal=lambda xform: self._move_form_refusal(
                    request, project, xform
                ),
            )
            if isinstance(survey, Response):
                return survey

            if isinstance(survey, XForm):
                if "formid" in request.data:
                    serializer_cls = XFormSerializer
                else:
                    serializer_cls = XFormCreateSerializer

                serializer = serializer_cls(survey, context={"request": request})

                published_by_formbuilder = request.data.get("published_by_formbuilder")

                if str_to_bool(published_by_formbuilder):
                    MetaData.published_by_formbuilder(survey, "True")
                    propagate_project_permissions_async.apply_async(
                        args=[project.id], countdown=30
                    )

                return Response(serializer.data, status=status.HTTP_201_CREATED)
            if survey["type"] and survey["text"]:
                error_message = f"{survey['type']}:{survey['text']}"
            else:
                error_message = f"{survey}"
            message_subject = "Failed to upload form"
            report_exception(message_subject, error_message)
            logger.info("%s: %s", message_subject, error_message)
            return Response(survey, status=status.HTTP_400_BAD_REQUEST)

        xforms = XForm.objects.filter(
            project=project,
            deleted_at__isnull=True,
            project__organization__is_active=True,
        )
        serializer = XFormSerializer(xforms, context={"request": request}, many=True)

        return Response(serializer.data)

    def _share_admin_refusal(self, request, validated_data):
        """An owner or manager can share the project on and delete it, so
        appointing one needs the caller's factor. Only for a target who does
        not already hold the role."""
        role_name = validated_data["role"]
        if role_name not in ADMIN_ROLE_NAMES:
            return None
        role = ROLES[role_name]
        targets = User.objects.filter(
            username__in=validated_data["username"].split(",")
        )
        if all(role.user_has_role(user, self.object) for user in targets):
            return None
        return self.check_step_up(request, GATE_SHARE_PROJECT_ADMIN)

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
            serializer = RemoveUserFromProjectSerializer(data={**data, remove: True})
        else:
            serializer = ShareProjectSerializer(data=data)
        if serializer.is_valid():
            if not remove:
                refusal = self._share_admin_refusal(request, serializer.validated_data)
                if refusal is not None:
                    return refusal
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
        clear_project_owner_cache(self.object.pk)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["DELETE", "GET", "POST"], detail=True)
    def star(self, request, *args, **kwargs):
        """
        Allows to add a user that stars a project.
        """
        user = request.user
        # pylint: disable=attribute-defined-outside-init
        self.object = project = self.get_object()

        if request.method == "DELETE":
            project.user_stars.remove(user)
        elif request.method == "POST":
            project.user_stars.add(user)
        elif request.method == "GET":
            users = project.user_stars.values("pk")
            user_profiles = UserProfile.objects.filter(user__in=users)
            serializer = UserProfileSerializer(
                user_profiles, context={"request": request}, many=True
            )

            return Response(serializer.data)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _invite_admin_refusal(self, request, validated_data, invitation=None):
        """An accepted invitation confers its role, so inviting an owner or
        manager needs the same factor as sharing with one. Pointing an admin
        invitation at another email invites someone new."""
        role = validated_data["role"]
        if role not in ADMIN_ROLE_NAMES:
            return None
        if (
            invitation is not None
            and invitation.role == role
            and invitation.email == validated_data["email"]
        ):
            return None
        return self.check_step_up(request, GATE_INVITE_PROJECT_ADMIN)

    @action(
        detail=True,
        methods=["GET", "POST", "PUT"],
        url_path="invitations",
    )
    def invitations(self, request, *args, **kwargs):
        """List, Create. Update project invitations"""
        project = self.get_object()
        method = request.method.upper()

        if method == "GET":
            invitations = project.invitations.all()
            invitation_status = request.query_params.get("status")

            if invitation_status:
                invitations = invitations.filter(status=invitation_status)

            serializer = self.get_serializer(invitations, many=True)
            return Response(serializer.data)

        if method == "POST":
            draft_request_data = self.request.data.copy()
            draft_request_data["project"] = project.pk
            data = draft_request_data
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            refusal = self._invite_admin_refusal(request, serializer.validated_data)
            if refusal is not None:
                return refusal
            serializer.save()
            return Response(serializer.data)

        if method == "PUT":
            invitation_id = request.data.get("invitation_id")
            try:
                invitation = get_object_or_404(
                    ProjectInvitation,
                    pk=invitation_id,
                    project=project,
                )
            except (ValueError, TypeError, OverflowError) as error:
                raise Http404 from error
            draft_request_data = self.request.data.copy()
            draft_request_data["project"] = project.pk
            data = draft_request_data
            serializer = self.get_serializer(
                invitation,
                data=data,
            )
            serializer.is_valid(raise_exception=True)
            refusal = self._invite_admin_refusal(
                request, serializer.validated_data, invitation
            )
            if refusal is not None:
                return refusal
            serializer.save()
            return Response(serializer.data)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["POST"], url_path="revoke-invitation")
    def revoke_invitation(self, request, *args, **kwargs):
        """Revoke a project  invitation object"""
        project = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "project": project},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": _("Success")})

    @action(detail=True, methods=["POST"], url_path="resend-invitation")
    def resend_invitation(self, request, *args, **kwargs):
        """Resend a project  invitation object"""
        project = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "project": project},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": _("Success")})

    def destroy(self, request, *args, **kwargs):
        """Soft deletes a project"""
        project = self.get_object()
        user = request.user
        project.soft_delete(user)

        return Response(status=status.HTTP_204_NO_CONTENT)
