# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""
The /forms API endpoint.
"""
import json
import os
import random
from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import IntegrityError
from django.db.models import Prefetch
from django.http import (HttpResponseBadRequest, HttpResponseForbidden,
                         HttpResponseRedirect, StreamingHttpResponse)
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.translation import gettext as _

import six
from django_filters.rest_framework import DjangoFilterBackend
from six.moves.urllib.parse import urlparse

try:
    from multidb.pinning import use_master
except ImportError:
    pass

from pyxform.builder import create_survey_element_from_dict
from pyxform.xls2json import parse_file_to_json
from rest_framework import exceptions, status
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.viewsets import ModelViewSet

from onadata.apps.api import tasks
from onadata.apps.api import tools as utils
from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models.xform import XForm, XFormUserObjectPermission
from onadata.apps.logger.models.xform_version import XFormVersion
from onadata.apps.logger.xform_instance_parser import XLSFormError
from onadata.apps.messaging.constants import FORM_UPDATED, XFORM
from onadata.apps.messaging.serializers import send_message
from onadata.apps.viewer.models.export import Export
from onadata.libs import authentication, filters
from onadata.libs.exceptions import EnketoError
from onadata.libs.mixins.anonymous_user_public_forms_mixin import \
    AnonymousUserPublicFormsMixin
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.labels_mixin import LabelsMixin
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.renderers import renderers
from onadata.libs.serializers.clone_xform_serializer import \
    CloneXFormSerializer
from onadata.libs.serializers.share_xform_serializer import \
    ShareXFormSerializer
from onadata.libs.serializers.xform_serializer import (
    XFormBaseSerializer, XFormCreateSerializer, XFormSerializer,
    XFormVersionListSerializer)
from onadata.libs.utils.api_export_tools import (_get_export_type,
                                                 custom_response_handler,
                                                 get_async_response,
                                                 get_existing_file_format,
                                                 process_async_export,
                                                 response_for_format)
from onadata.libs.utils.cache_tools import PROJ_OWNER_CACHE, safe_delete
from onadata.libs.utils.common_tools import json_stream
from onadata.libs.utils.csv_import import (get_async_csv_submission_status,
                                           submission_xls_to_csv, submit_csv,
                                           submit_csv_async)
from onadata.libs.utils.export_tools import parse_request_export_options
from onadata.libs.utils.logger_tools import publish_form
from onadata.libs.utils.string import str2bool
from onadata.libs.utils.viewer_tools import (generate_enketo_form_defaults,
                                             get_enketo_urls, get_form_url)
from onadata.settings.common import CSV_EXTENSION, XLS_EXTENSIONS

# pylint: disable=invalid-name
BaseViewset = get_baseviewset_class()
User = get_user_model()


def upload_to_survey_draft(filename, username):
    """Return the ``filename`` in the ``username`` survey-drafts directory."""
    return os.path.join(username, "survey-drafts", os.path.split(filename)[1])


def get_survey_dict(csv_name):
    """Returns the a CSV XLSForm file into a python object."""
    survey_file = default_storage.open(csv_name, "rb")

    survey_dict = parse_file_to_json(survey_file.name, default_name="data")

    return survey_dict


def _get_user(username):
    users = User.objects.filter(username__iexact=username)

    return users[0] if users.count() else None


def _get_owner(request):
    owner = request.data.get("owner") or request.user

    if isinstance(owner, six.string_types):
        owner_obj = _get_user(owner)

        if owner_obj is None:
            raise ValidationError(f"User with username {owner} does not exist.")
        owner = owner_obj

    return owner


def value_for_type(form, field, value):
    """Returns a boolean value for the ``field`` of type ``BooleanField`` otherwise
    returns the same ``value`` back."""
    if form._meta.get_field(field).get_internal_type() == "BooleanField":
        return str2bool(value)

    return value


def _try_update_xlsform(request, xform, owner):
    survey = utils.publish_xlsform(request, owner, xform.id_string, xform.project)

    if isinstance(survey, XForm):
        serializer = XFormSerializer(xform, context={"request": request})

        # send form update notification
        send_message(
            instance_id=xform.id,
            target_id=xform.id,
            target_type=XFORM,
            user=request.user or owner,
            message_verb=FORM_UPDATED,
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    return Response(survey, status=status.HTTP_400_BAD_REQUEST)


def result_has_error(result):
    """Returns True if the ``result`` is a dict and has a type."""
    return isinstance(result, dict) and result.get("type")


def get_survey_xml(csv_name):
    """Creates and returns the XForm XML from a CSV XLSform."""
    survey_dict = get_survey_dict(csv_name)
    survey = create_survey_element_from_dict(survey_dict)
    return survey.to_xml()


def parse_webform_return_url(return_url, request):
    """
    Given a webform url and request containing authentication information
    extract authentication data encoded in the url and validate using either
    this data or data in the request. Construct a proper return URL, which has
    stripped the authentication data, to return the user.
    """

    jwt_param = None
    url = urlparse(return_url)
    try:
        # get jwt from url - probably zebra via enketo
        jwt_param = [p for p in url.query.split("&") if p.startswith("jwt")]
        jwt_param = jwt_param and jwt_param[0].split("=")[1]

        if not jwt_param:
            return None
    except IndexError:
        pass

    if "/_/" in return_url:  # offline url
        redirect_url = f"{url.scheme}://{url.netloc}{url.path}#{url.fragment}"
    elif "/::" in return_url:  # non-offline url
        redirect_url = f"{url.scheme}://{url.netloc}{url.path}"
    else:
        # unexpected format
        return None

    response_redirect = HttpResponseRedirect(redirect_url)

    # if the requesting user is not authenticated but the token has been
    # retrieved from the url - probably zebra via enketo express - use the
    # token to create signed cookies which will be used by subsequent
    # enketo calls to authenticate the user
    if jwt_param:
        username = None
        if request.user.is_anonymous:
            api_token = authentication.get_api_token(jwt_param)
            if getattr(api_token, "user"):
                username = api_token.user.username
        else:
            username = request.user.username

        response_redirect = utils.set_enketo_signed_cookies(
            response_redirect, username=username, json_web_token=jwt_param
        )

        return response_redirect
    return None


# pylint: disable=too-many-ancestors
class XFormViewSet(
    AnonymousUserPublicFormsMixin,
    CacheControlMixin,
    AuthenticateHeaderMixin,
    ETagsMixin,
    LabelsMixin,
    BaseViewset,
    ModelViewSet,
):
    """
    Publish XLSForms, List, Retrieve Published Forms.
    """

    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        renderers.XLSRenderer,
        renderers.XLSXRenderer,
        renderers.CSVRenderer,
        renderers.CSVZIPRenderer,
        renderers.SAVZIPRenderer,
        renderers.SurveyRenderer,
        renderers.OSMExportRenderer,
        renderers.ZipRenderer,
        renderers.GoogleSheetsRenderer,
    ]
    queryset = (
        XForm.objects.select_related("user", "created_by")
        .prefetch_related(
            Prefetch(
                "xformuserobjectpermission_set",
                queryset=XFormUserObjectPermission.objects.select_related(
                    "user__profile__organizationprofile", "permission"
                ),
            ),
            Prefetch("metadata_set"),
            Prefetch("tags"),
            Prefetch("dataview_set"),
        )
        .only(
            "id",
            "id_string",
            "title",
            "shared",
            "shared_data",
            "require_auth",
            "created_by",
            "num_of_submissions",
            "downloadable",
            "encrypted",
            "sms_id_string",
            "date_created",
            "date_modified",
            "last_submission_time",
            "uuid",
            "bamboo_dataset",
            "instances_with_osm",
            "instances_with_geopoints",
            "version",
            "has_hxl_support",
            "project",
            "last_updated_at",
            "user",
            "allows_sms",
            "description",
            "is_merged_dataset",
        )
    )
    serializer_class = XFormSerializer
    pagination_class = StandardPageNumberPagination
    lookup_field = "pk"
    extra_lookup_fields = None
    permission_classes = [
        XFormPermissions,
    ]
    updatable_fields = set(
        (
            "description",
            "downloadable",
            "require_auth",
            "shared",
            "shared_data",
            "title",
        )
    )
    filter_backends = (
        filters.EnketoAnonDjangoObjectPermissionFilter,
        filters.TagFilter,
        filters.XFormOwnerFilter,
        DjangoFilterBackend,
    )
    filterset_fields = ("instances_with_osm",)

    public_forms_endpoint = "public"

    def get_serializer_class(self):
        if self.action == "list":
            return XFormBaseSerializer

        return super().get_serializer_class()

    # pylint: disable=unused-argument
    def create(self, request, *args, **kwargs):
        """Support XLSForm publishing endpoint `POST /api/v1/forms`."""
        try:
            owner = _get_owner(request)
        except ValidationError as e:
            return Response(
                {"message": e.messages[0]}, status=status.HTTP_400_BAD_REQUEST
            )

        survey = utils.publish_xlsform(request, owner)
        if isinstance(survey, XForm):
            # survey is a DataDictionary we need an XForm to return the correct
            # role for the user after form publishing.
            serializer = XFormCreateSerializer(survey, context={"request": request})
            headers = self.get_success_headers(serializer.data)

            return Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )

        return Response(survey, status=status.HTTP_400_BAD_REQUEST)

    # pylint: disable=unused-argument
    @action(methods=["POST", "GET"], detail=False)
    def create_async(self, request, *args, **kwargs):
        """Temporary Endpoint for Async form creation"""
        resp = headers = {}
        resp_code = status.HTTP_400_BAD_REQUEST

        if request.method == "GET":
            # pylint: disable=attribute-defined-outside-init
            self.etag_data = f"{timezone.now()}"
            survey = tasks.get_async_status(request.query_params.get("job_uuid"))

            if "pk" in survey:
                xform = XForm.objects.get(pk=survey.get("pk"))
                serializer = XFormSerializer(xform, context={"request": request})
                headers = self.get_success_headers(serializer.data)
                resp = serializer.data
                resp_code = status.HTTP_201_CREATED
            else:
                resp_code = status.HTTP_202_ACCEPTED
                resp.update(survey)
        else:
            try:
                owner = _get_owner(request)
            except ValidationError as e:
                return Response(
                    {"message": e.messages[0]}, status=status.HTTP_400_BAD_REQUEST
                )

            fname = request.FILES.get("xls_file").name
            if isinstance(request.FILES.get("xls_file"), InMemoryUploadedFile):
                xls_file_path = default_storage.save(
                    f"tmp/async-upload-{owner.username}-{fname}",
                    ContentFile(request.FILES.get("xls_file").read()),
                )
            else:
                xls_file_path = request.FILES.get("xls_file").temporary_file_path()

            resp.update(
                {
                    "job_uuid": tasks.publish_xlsform_async.delay(
                        request.user.id,
                        request.POST,
                        owner.id,
                        {"name": fname, "path": xls_file_path},
                    ).task_id
                }
            )
            resp_code = status.HTTP_202_ACCEPTED

        return Response(data=resp, status=resp_code, headers=headers)

    @action(methods=["GET", "HEAD"], detail=True)
    def form(self, request, **kwargs):
        """Returns the XLSForm in any of JSON, XML, XLS(X), CSV formats."""
        form = self.get_object()
        form_format = kwargs.get("format", "json")
        if form_format not in ["json", "xml", "xls", "xlsx", "csv"]:
            return HttpResponseBadRequest(
                "400 BAD REQUEST", content_type="application/json", status=400
            )
        # pylint: disable=attribute-defined-outside-init
        self.etag_data = f"{form.date_modified}"
        response = response_for_format(form, format=form_format)

        # add backward compatibility for existing .xls forms
        form_format = get_existing_file_format(form.xls, form_format)
        filename = form.id_string + "." + form_format
        response["Content-Disposition"] = "attachment; filename=" + filename

        return response

    # pylint: disable=unused-argument
    @action(methods=["GET"], detail=False)
    def login(self, request, **kwargs):
        """Authenticate and redirect to URL in `return` query parameter."""
        return_url = request.query_params.get("return")

        if return_url:
            redirect = parse_webform_return_url(return_url, request)

            if redirect:
                return redirect

            # get value of login URL based on host
            host = request.get_host()
            enketo_client_login_url_setting = settings.ENKETO_CLIENT_LOGIN_URL or {}
            enketo_client_login_url = (
                host in enketo_client_login_url_setting
                and enketo_client_login_url_setting[host]
            ) or (
                "*" in enketo_client_login_url_setting
                and enketo_client_login_url_setting["*"]
            )
            login_vars = {
                "login_url": enketo_client_login_url,
                "return_url": urlencode({"return_url": return_url}),
            }
            client_login = "{login_url}?{return_url}".format(**login_vars)

            return HttpResponseRedirect(client_login)

        return HttpResponseForbidden("Authentication failure, cannot redirect")

    # pylint: disable=unused-argument
    @action(methods=["GET"], detail=True)
    def enketo(self, request, **kwargs):
        """Expose enketo urls."""
        survey_type = self.kwargs.get("survey_type") or request.GET.get("survey_type")
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        form_url = get_form_url(
            request,
            self.object.user.username,
            protocol=settings.ENKETO_PROTOCOL,
            xform_pk=self.object.pk,
            generate_consistent_urls=True,
        )

        data = {"message": _("Enketo not properly configured.")}
        http_status = status.HTTP_400_BAD_REQUEST

        try:
            # pass default arguments to enketo_url to prepopulate form fields
            request_vars = request.GET
            defaults = generate_enketo_form_defaults(self.object, **request_vars)
            enketo_urls = get_enketo_urls(form_url, self.object.id_string, **defaults)
            offline_url = enketo_urls.get("offline_url")
            preview_url = enketo_urls.get("preview_url")
            single_submit_url = enketo_urls.get("single_url")
        except EnketoError as e:
            data = {"message": _(f"Enketo error: {e}")}
        else:
            if survey_type == "single":
                http_status = status.HTTP_200_OK
                data = {"single_submit_url": single_submit_url}
            else:
                http_status = status.HTTP_200_OK
                data = {
                    "enketo_url": offline_url,
                    "enketo_preview_url": preview_url,
                    "single_submit_url": single_submit_url,
                }

        return Response(data, http_status)

    # pylint: disable=unused-argument
    @action(methods=["POST", "GET"], detail=False)
    def survey_preview(self, request, **kwargs):
        """Handle survey preview XLSForms."""
        username = request.user.username
        if request.method.upper() == "POST":
            if not username:
                raise ParseError("User has to be authenticated")

            csv_data = request.data.get("body")
            if csv_data:
                random_name = "".join(
                    random.sample("abcdefghijklmnopqrstuvwxyz0123456789", 6)
                )
                rand_name = f"survey_draft_{random_name}.csv"
                csv_file = ContentFile(csv_data)
                csv_name = default_storage.save(
                    upload_to_survey_draft(rand_name, username), csv_file
                )

                result = publish_form(lambda: get_survey_xml(csv_name))

                if result_has_error(result):
                    raise ParseError(result.get("text"))

                return Response(
                    {"unique_string": rand_name, "username": username}, status=200
                )
            raise ParseError("Missing body")

        filename = request.query_params.get("filename")
        username = request.query_params.get("username")

        if not username:
            raise ParseError("Username not provided")
        if not filename:
            raise ParseError("Filename MUST be provided")

        csv_name = upload_to_survey_draft(filename, username)
        result = publish_form(lambda: get_survey_xml(csv_name))
        if result_has_error(result):
            raise ParseError(result.get("text"))

        # pylint: disable=attribute-defined-outside-init
        self.etag_data = result

        return Response(result, status=200)

    def retrieve(self, request, *args, **kwargs):
        """Returns a forms properties."""
        lookup_field = self.lookup_field
        lookup = self.kwargs.get(lookup_field)

        if lookup == self.public_forms_endpoint:
            # pylint: disable=attribute-defined-outside-init
            self.object_list = self._get_public_forms_queryset()

            page = self.paginate_queryset(self.object_list.order_by("pk"))
            if page is not None:
                serializer = self.get_serializer(page, many=True)
            else:
                serializer = self.get_serializer(self.object_list, many=True)

            return Response(serializer.data)

        xform = self.get_object()
        export_type = kwargs.get("format") or request.query_params.get("format")
        query = request.query_params.get("query")
        token = request.GET.get("token")
        meta = request.GET.get("meta")

        if export_type is None or export_type in ["json", "debug"]:
            # perform default viewset retrieve, no data export
            return super().retrieve(request, *args, **kwargs)

        return custom_response_handler(
            request,
            xform,
            query,
            export_type,
            token,
            meta,
        )

    @action(methods=["POST"], detail=True)
    def share(self, request, *args, **kwargs):
        """Perform form sharing."""
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()

        usernames_str = request.data.get("usernames", request.data.get("username"))

        if not usernames_str:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        role = request.data.get("role")  # the serializer validates the role
        xform_id = self.object.pk
        data_list = [
            {"xform": xform_id, "username": username, "role": role}
            for username in usernames_str.split(",")
        ]

        serializer = ShareXFormSerializer(data=data_list, many=True)

        if serializer.is_valid():
            serializer.save()
        else:
            return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["POST"], detail=True)
    def clone(self, request, *args, **kwargs):
        """Clone/duplicate an existing form."""
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        data = {"xform": self.object.pk, "username": request.data.get("username")}
        project = request.data.get("project_id")
        if project:
            data["project"] = project
        serializer = CloneXFormSerializer(data=data)
        if serializer.is_valid():
            clone_to_user = User.objects.get(username=data["username"])
            if not request.user.has_perm("can_add_xform", clone_to_user.profile):
                user = request.user.username
                account = data["username"]
                raise exceptions.PermissionDenied(
                    detail=_(
                        f"User {user} has no permission to add "
                        f"xforms to account {account}"
                    )
                )
            try:
                xform = serializer.save()
            except IntegrityError as e:
                raise ParseError(
                    "A clone with the same id_string has already been created"
                ) from e
            serializer = XFormSerializer(
                xform.cloned_form, context={"request": request}
            )

            return Response(data=serializer.data, status=status.HTTP_201_CREATED)

        return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["POST", "GET"], detail=True, url_name="import", url_path="import")
    def data_import(self, request, *args, **kwargs):
        """Endpoint for CSV and XLS data imports
        Calls :py:func:`onadata.libs.utils.csv_import.submit_csv` for POST
        requests passing the `request.FILES.get('csv_file')` upload
        for import and
        :py:func:onadata.libs.utils.csv_import.get_async_csv_submission_status
        for GET requests passing `job_uuid` query param for job progress
        polling and
        :py:func:`onadata.libs.utils.csv_import.submission_xls_to_csv`
        for POST request passing the `request.FILES.get('xls_file')` upload for
        import if xls_file is provided instead of csv_file
        """
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        resp = {}
        if request.method == "GET":
            try:
                resp.update(
                    get_async_csv_submission_status(
                        request.query_params.get("job_uuid")
                    )
                )
                self.last_modified_date = timezone.now()
            except ValueError as e:
                raise ParseError(
                    (
                        "The instance of the result is not a "
                        "basestring; the job_uuid variable might "
                        "be incorrect"
                    )
                ) from e
        else:
            csv_file = request.FILES.get("csv_file", None)
            xls_file = request.FILES.get("xls_file", None)

            if csv_file is None and xls_file is None:
                resp.update({"error": "csv_file and xls_file field empty"})

            elif xls_file and xls_file.name.split(".")[-1] not in XLS_EXTENSIONS:
                resp.update({"error": "xls_file not an excel file"})

            elif csv_file and csv_file.name.split(".")[-1] != CSV_EXTENSION:
                resp.update({"error": "csv_file not a csv file"})

            else:
                if xls_file and xls_file.name.split(".")[-1] in XLS_EXTENSIONS:
                    csv_file = submission_xls_to_csv(xls_file)
                overwrite = request.query_params.get("overwrite")
                overwrite = (
                    overwrite.lower() == "true"
                    if isinstance(overwrite, str)
                    else overwrite
                )
                size_threshold = settings.CSV_FILESIZE_IMPORT_ASYNC_THRESHOLD
                try:
                    csv_size = csv_file.size
                except AttributeError:
                    csv_size = csv_file.__sizeof__()
                if csv_size < size_threshold:
                    resp.update(
                        submit_csv(
                            request.user.username, self.object, csv_file, overwrite
                        )
                    )
                else:
                    csv_file.seek(0)
                    file_name = getattr(csv_file, "name", xls_file and xls_file.name)
                    upload_to = os.path.join(
                        request.user.username, "csv_imports", file_name
                    )
                    file_name = default_storage.save(upload_to, csv_file)
                    task = submit_csv_async.delay(
                        request.user.username, self.object.pk, file_name, overwrite
                    )
                    if task is None:
                        raise ParseError("Task not found")
                    resp.update({"task_id": task.task_id})

        return Response(
            data=resp,
            status=(
                status.HTTP_200_OK
                if resp.get("error") is None
                else status.HTTP_400_BAD_REQUEST
            ),
        )

    @action(methods=["POST", "GET"], detail=True)
    def csv_import(self, request, *args, **kwargs):
        """Endpoint for CSV data imports
        Calls :py:func:`onadata.libs.utils.csv_import.submit_csv` for POST
        requests passing the `request.FILES.get('csv_file')` upload
        for import and
        :py:func:onadata.libs.utils.csv_import.get_async_csv_submission_status
        for GET requests passing `job_uuid` query param for job progress
        polling
        """
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        resp = {}
        if request.method == "GET":
            try:
                resp.update(
                    get_async_csv_submission_status(
                        request.query_params.get("job_uuid")
                    )
                )
                # pylint: disable=attribute-defined-outside-init
                self.last_modified_date = timezone.now()
            except ValueError as e:
                raise ParseError(
                    (
                        "The instance of the result is not a "
                        "basestring; the job_uuid variable might "
                        "be incorrect"
                    )
                ) from e
        else:
            csv_file = request.FILES.get("csv_file", None)
            if csv_file is None:
                resp.update({"error": "csv_file field empty"})
            elif csv_file.name.split(".")[-1] != CSV_EXTENSION:
                resp.update({"error": "csv_file not a csv file"})
            else:
                overwrite = request.query_params.get("overwrite")
                overwrite = (
                    overwrite.lower() == "true"
                    if isinstance(overwrite, str)
                    else overwrite
                )
                size_threshold = settings.CSV_FILESIZE_IMPORT_ASYNC_THRESHOLD
                if csv_file.size < size_threshold:
                    resp.update(
                        submit_csv(
                            request.user.username, self.object, csv_file, overwrite
                        )
                    )
                else:
                    csv_file.seek(0)
                    upload_to = os.path.join(
                        request.user.username, "csv_imports", csv_file.name
                    )
                    file_name = default_storage.save(upload_to, csv_file)
                    task = submit_csv_async.delay(
                        request.user.username, self.object.pk, file_name, overwrite
                    )
                    if task is None:
                        raise ParseError("Task not found")
                    resp.update({"task_id": task.task_id})

        return Response(
            data=resp,
            status=(
                status.HTTP_200_OK
                if resp.get("error") is None
                else status.HTTP_400_BAD_REQUEST
            ),
        )

    def partial_update(self, request, *args, **kwargs):
        """Partial update of a form's properties."""
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        owner = self.object.user

        # updating the file
        if request.FILES or set(["xls_url", "dropbox_xls_url", "text_xls_form"]) & set(
            request.data
        ):
            return _try_update_xlsform(request, self.object, owner)

        try:
            return super().partial_update(request, *args, **kwargs)
        except XLSFormError as e:
            raise ParseError(str(e)) from e

    @action(methods=["DELETE", "GET"], detail=True)
    def delete_async(self, request, *args, **kwargs):
        """Delete asynchronous endpoint `/api/v1/forms/{pk}/delete_async`."""
        resp = {}
        resp_code = status.HTTP_400_BAD_REQUEST
        if request.method == "DELETE":
            xform = self.get_object()
            resp = {
                "job_uuid": tasks.delete_xform_async.delay(
                    xform.pk, request.user.id
                ).task_id,
                "time_async_triggered": datetime.now(),
            }

            # clear project from cache
            safe_delete(f"{PROJ_OWNER_CACHE}{xform.project.pk}")
            resp_code = status.HTTP_202_ACCEPTED

        if request.method == "GET":
            job_uuid = request.query_params.get("job_uuid")
            resp = tasks.get_async_status(job_uuid)
            resp_code = status.HTTP_202_ACCEPTED
            # pylint: disable=attribute-defined-outside-init
            self.etag_data = f"{timezone.now()}"

        return Response(data=resp, status=resp_code)

    def destroy(self, request, *args, **kwargs):
        """Soft deletes a form - `DELETE /api/v1/forms/{pk}`"""
        xform = self.get_object()
        user = request.user
        xform.soft_delete(user=user)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["GET"], detail=True)
    def versions(self, request, *args, **kwargs):
        """Returns all form versions."""
        xform = self.get_object()
        version_id = kwargs.get("version_id")
        requested_format = kwargs.get("format") or "json"

        if version_id:
            version = get_object_or_404(XFormVersion, version=version_id, xform=xform)
            return response_for_format(version, format=requested_format)

        queryset = XFormVersion.objects.filter(xform=xform)
        serializer = XFormVersionListSerializer(
            queryset, many=True, context={"request": request}
        )

        return Response(data=serializer.data, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=True)
    def export_async(self, request, *args, **kwargs):
        """Returns the status of an async export."""
        xform = self.get_object()
        export_type = request.query_params.get("format")

        if export_type:
            try:
                _get_export_type(export_type)

            except exceptions.ParseError:
                payload = {"details": _("Export format not supported")}
                return Response(
                    data=payload,
                    status=status.HTTP_403_FORBIDDEN,
                    content_type="application/json",
                )

        job_uuid = request.query_params.get("job_uuid")

        if export_type in ["csvzip", "savzip"]:
            # Overide renderer and mediatype because all response are
            # suppose to be in json
            # TODO: Avoid overiding the format query param for export type
            #  DRF uses format to select the renderer
            self.request.accepted_renderer = renderers.JSONRenderer()
            self.request.accepted_mediatype = "application/json"

        if job_uuid:
            try:
                resp = get_async_response(job_uuid, request, xform)
            except Export.DoesNotExist:
                # if this does not exist retry it against the primary
                try:
                    with use_master:
                        resp = get_async_response(job_uuid, request, xform)
                except NameError:
                    resp = get_async_response(job_uuid, request, xform)
        else:
            query = request.query_params.get("query")
            token = request.query_params.get("token")
            meta = request.query_params.get("meta")
            data_id = request.query_params.get("data_id")
            options = parse_request_export_options(request.query_params)
            options["host"] = request.get_host()
            options.update(
                {
                    "meta": meta,
                    "token": token,
                    "data_id": data_id,
                }
            )

            if query:
                options.update({"query": query})

            resp = process_async_export(request, xform, export_type, options)

            if isinstance(resp, HttpResponseRedirect):
                payload = {"details": _("Google authorization needed"), "url": resp.url}
                return Response(
                    data=payload,
                    status=status.HTTP_403_FORBIDDEN,
                    content_type="application/json",
                )

        # pylint: disable=attribute-defined-outside-init
        self.etag_data = f"{timezone.now()}"

        return Response(
            data=resp,
            status=status.HTTP_202_ACCEPTED,
            content_type="application/json",
        )

    def _get_streaming_response(self):
        """
        Get a StreamingHttpResponse response object
        """
        # use queryset_iterator.  Will need to change this to the Django
        # native .iterator() method when we upgrade to django version 2
        # because in Django 2 .iterator() has support for chunk size
        queryset = self.object_list.instance

        def get_json_string(item):
            return json.dumps(
                XFormBaseSerializer(
                    instance=item, context={"request": self.request}
                ).data
            )

        # pylint: disable=http-response-with-content-type-json
        response = StreamingHttpResponse(
            json_stream(queryset, get_json_string), content_type="application/json"
        )

        # calculate etag value and add it to response headers
        if hasattr(self, "etag_data"):
            self.set_etag_header(None, self.etag_data)

        self.set_cache_control(response)

        # set headers on streaming response
        for k, v in self.headers.items():
            response[k] = v

        return response

    def list(self, request, *args, **kwargs):
        """List forms API endpoint `GET /api/v1/forms`."""
        stream_data = getattr(settings, "STREAM_DATA", False)
        # pylint: disable=attribute-defined-outside-init
        try:
            self.object_list = self.filter_queryset(self.get_queryset())
            last_modified = self.object_list.values_list(
                "date_modified", flat=True
            ).order_by("-date_modified")
            page = self.paginate_queryset(self.object_list)
            if last_modified:
                self.etag_data = last_modified[0].isoformat()
            if page:
                self.object_list = self.get_serializer(page, many=True)
            else:
                self.object_list = self.get_serializer(self.object_list, many=True)
            if stream_data:
                resp = self._get_streaming_response()
            else:
                serializer = self.object_list
                resp = Response(serializer.data, status=status.HTTP_200_OK)
        except XLSFormError as e:
            resp = HttpResponseBadRequest(e)

        return resp
