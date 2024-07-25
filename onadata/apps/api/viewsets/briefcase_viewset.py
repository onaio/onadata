# -*- coding: utf-8 -*-
"""
The /briefcase API implementation.
"""
from xml.dom import NotFoundErr

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.validators import ValidationError
from django.db import OperationalError
from django.http import Http404
from django.utils.translation import gettext as _

import six
from rest_framework import exceptions, mixins, permissions, status, viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.response import Response

from onadata.apps.api.permissions import ViewDjangoObjectPermissions
from onadata.apps.api.tools import get_media_file_response
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.xform_instance_parser import clean_and_parse_xml
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs import filters
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.mixins.openrosa_headers_mixin import get_openrosa_headers
from onadata.libs.renderers.renderers import TemplateXMLRenderer
from onadata.libs.serializers.xform_serializer import (
    XFormListSerializer,
    XFormManifestSerializer,
)
from onadata.libs.utils.logger_tools import PublishXForm, publish_form
from onadata.libs.utils.viewer_tools import get_form

# pylint: disable=invalid-name
User = get_user_model()


def _extract_uuid(text):
    if isinstance(text, six.string_types):
        form_id_parts = text.split("/")

        if len(form_id_parts) < 2:
            raise ValidationError(_(f"Invalid formId {text}."))

        text = form_id_parts[1]
        text = text[text.find("@key=") : -1].replace("@key=", "")

        if text.startswith("uuid:"):
            text = text.replace("uuid:", "")

    return text


def _extract_id_string(id_string):
    if isinstance(id_string, six.string_types):
        return id_string[0 : id_string.find("[")]

    return id_string


def _parse_int(num):
    try:
        return num and int(num)
    except ValueError:
        return None


def _query_optimization_fence(instances, num_entries):
    """
    Enhances query performance by using an optimization fence.

    This utility function creates an optimization fence around the provided
    queryset instances. It encapsulates the original query within a
    SELECT statement with an ORDER BY and LIMIT clause,
    optimizing the database query for improved performance.

    Parameters:
    - instances: QuerySet
        The input QuerySet of instances to be optimized.
    - num_entries: int
        The number of instances to be included in the optimized result set.

    Returns:
    QuerySet
        An optimized QuerySet containing selected fields ('pk' and 'uuid')
        based on the provided instances.
    """
    inner_raw_sql = str(instances.query)

    # Create the outer query with the LIMIT clause
    outer_query = (
        f"SELECT id, uuid FROM ({inner_raw_sql}) AS items "  # nosec
        "ORDER BY id ASC LIMIT %s"  # nosec
    )
    raw_queryset = Instance.objects.raw(outer_query, [num_entries])
    # convert raw queryset to queryset
    instances_data = [
        {"pk": item.id, "uuid": item.uuid}
        for item in raw_queryset.iterator()
    ]
    # Create QuerySet from the instances dict
    instances = Instance.objects.filter(
        pk__in=[item["pk"] for item in instances_data]
    ).values("pk", "uuid")

    return instances


# pylint: disable=too-many-ancestors
class BriefcaseViewset(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Implements the [Briefcase Aggregate API](\
    https://code.google.com/p/opendatakit/wiki/BriefcaseAggregateAPI).
    """

    authentication_classes = (DigestAuthentication, TokenAuthentication,)
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    queryset = XForm.objects.all()
    permission_classes = (permissions.IsAuthenticated, ViewDjangoObjectPermissions)
    renderer_classes = (TemplateXMLRenderer, BrowsableAPIRenderer)
    serializer_class = XFormListSerializer
    template_name = "openrosa_response.xml"

    # pylint: disable=unused-argument
    def get_object(self, queryset=None):
        """Returns an Instance submission object for the given UUID."""
        form_id = self.request.GET.get("formId", "")
        id_string = _extract_id_string(form_id)
        uuid = _extract_uuid(form_id)
        username = self.kwargs.get("username")
        form_pk = self.kwargs.get("xform_pk")
        project_pk = self.kwargs.get("project_pk")

        if not username:
            if form_pk:
                queryset = self.queryset.filter(pk=form_pk)
                if queryset.first():
                    username = queryset.first().user.username
            elif project_pk:
                queryset = self.queryset.filter(project__pk=project_pk)
                if queryset.first():
                    username = queryset.first().user.username

        obj = get_object_or_404(
            Instance,
            xform__user__username__iexact=username,
            xform__id_string__iexact=id_string,
            uuid=uuid,
        )
        self.check_object_permissions(self.request, obj.xform)

        return obj

    # pylint: disable=too-many-branches,too-many-statements,too-many-locals
    def filter_queryset(self, queryset):
        """
        Filters an XForm submission instances using ODK Aggregate query parameters.
        """
        username = self.kwargs.get("username")
        form_pk = self.kwargs.get("xform_pk")
        project_pk = self.kwargs.get("project_pk")

        if (
            not username or not form_pk or not project_pk
        ) and self.request.user.is_anonymous:
            # raises a permission denied exception, forces authentication
            self.permission_denied(self.request)

        if username is not None and self.request.user.is_anonymous:
            profile = None
            if username:
                profile = get_object_or_404(
                    UserProfile, user__username__iexact=username
                )
            elif form_pk:
                queryset = queryset.filter(pk=form_pk)
                if queryset.first():
                    profile = queryset.first().user.profile
            elif project_pk:
                queryset = queryset.filter(project__pk=project_pk)
                if queryset.first():
                    profile = queryset.first().user.profile

            if profile.require_auth:
                # raises a permission denied exception, forces authentication
                self.permission_denied(self.request)
            else:
                queryset = queryset.filter(user=profile.user)
        elif form_pk:
            queryset = queryset.filter(pk=form_pk)
        elif project_pk:
            queryset = queryset.filter(project__pk=project_pk)
        else:
            queryset = super().filter_queryset(queryset)

        id_string = self.request.GET.get("formId", "")

        if id_string.find("[") != -1:
            id_string = _extract_id_string(id_string)

        xform_kwargs = {"queryset": queryset, "id_string__iexact": id_string}
        if username:
            xform_kwargs["user__username__iexact"] = username
        xform = get_form(xform_kwargs)
        self.check_object_permissions(self.request, xform)
        instances = Instance.objects.filter(
            xform=xform, deleted_at__isnull=True
        ).values("pk", "uuid")
        if xform.encrypted:
            instances = instances.filter(media_all_received=True)
        instances = instances.order_by("pk")
        num_entries = self.request.GET.get("numEntries")
        cursor = self.request.GET.get("cursor")

        cursor = _parse_int(cursor)
        if cursor:
            instances = instances.filter(pk__gt=cursor)

        num_entries = _parse_int(num_entries)
        if num_entries:
            try:
                paginated_instances = instances[:num_entries]
                # trigger a database call
                _ = len(paginated_instances)
                instances = paginated_instances
            except OperationalError:
                instances = _query_optimization_fence(instances, num_entries)

        # Using len() instead of .count() to prevent an extra
        # database call; len() will load the instances in memory allowing
        # us to pre-load the queryset before generating the response
        # and removes the need to perform a count on the database.
        instance_count = len(instances)

        # pylint: disable=attribute-defined-outside-init
        if instance_count > 0:
            last_instance = instances[instance_count - 1]
            self.resumption_cursor = last_instance.get("pk")
        elif instance_count == 0 and cursor:
            self.resumption_cursor = cursor
        else:
            self.resumption_cursor = 0

        return instances

    def create(self, request, *args, **kwargs):
        """Accepts an XForm XML and publishes it as a form."""
        if request.method.upper() == "HEAD":
            return Response(
                status=status.HTTP_204_NO_CONTENT,
                headers=get_openrosa_headers(request),
                template_name=self.template_name,
            )

        xform_def = request.FILES.get("form_def_file", None)
        response_status = status.HTTP_201_CREATED
        username = kwargs.get("username")
        form_user = (
            get_object_or_404(User, username=username) if username else request.user
        )

        if not request.user.has_perm("can_add_xform", form_user.profile):
            raise exceptions.PermissionDenied(
                detail=_(
                    "User %(user)s has no permission to add xforms to "
                    "account %(account)s"
                    % {"user": request.user.username, "account": form_user.username}
                )
            )
        data = {}

        if isinstance(xform_def, File):
            do_form_upload = PublishXForm(xform_def, form_user)
            data_dictionary = publish_form(do_form_upload.publish_xform)

            if isinstance(data_dictionary, XForm):
                data["message"] = _(
                    f"{data_dictionary.id_string} successfully published."
                )
            else:
                data["message"] = data_dictionary["text"]
                response_status = status.HTTP_400_BAD_REQUEST
        else:
            data["message"] = _("Missing xml file.")
            response_status = status.HTTP_400_BAD_REQUEST

        return Response(
            data,
            status=response_status,
            headers=get_openrosa_headers(request, location=False),
            template_name=self.template_name,
        )

    def list(self, request, *args, **kwargs):
        """Returns a list of submissions with reference submission download."""
        # pylint: disable=attribute-defined-outside-init
        self.object_list = self.filter_queryset(self.get_queryset())

        data = {
            "instances": self.object_list,
            "resumptionCursor": self.resumption_cursor,
        }

        return Response(
            data,
            headers=get_openrosa_headers(request, location=False),
            template_name="submissionList.xml",
        )

    def retrieve(self, request, *args, **kwargs):
        """Returns a single submission XML for download."""
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()

        xml_obj = clean_and_parse_xml(self.object.xml)
        submission_xml_root_node = xml_obj.documentElement
        submission_xml_root_node.setAttribute("instanceID", f"uuid:{self.object.uuid}")
        submission_xml_root_node.setAttribute(
            "submissionDate", self.object.date_created.isoformat()
        )

        if getattr(settings, "SUPPORT_BRIEFCASE_SUBMISSION_DATE", True):
            # Remove namespace attribute if any
            try:
                submission_xml_root_node.removeAttribute("xmlns")
            except NotFoundErr:
                pass

        data = {
            "submission_data": submission_xml_root_node.toxml(),
            "media_files": Attachment.objects.filter(instance=self.object),
            "host": request.build_absolute_uri().replace(request.get_full_path(), ""),
        }

        return Response(
            data,
            headers=get_openrosa_headers(request, location=False),
            template_name="downloadSubmission.xml",
        )

    @action(methods=["GET"], detail=True)
    def manifest(self, request, *args, **kwargs):
        """Returns list of media content."""
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        object_list = MetaData.objects.filter(
            data_type="media", object_id=self.object.id
        )
        context = self.get_serializer_context()
        serializer = XFormManifestSerializer(object_list, many=True, context=context)

        return Response(
            serializer.data, headers=get_openrosa_headers(request, location=False)
        )

    @action(methods=["GET"], detail=True)
    def media(self, request, *args, **kwargs):
        """Returns a single media content."""
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        metadata_pk = kwargs.get("metadata")

        if not metadata_pk:
            raise Http404()

        meta_obj = get_object_or_404(
            MetaData, data_type="media", xform=self.object, pk=metadata_pk
        )

        return get_media_file_response(meta_obj)
