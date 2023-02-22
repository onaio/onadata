# -*- coding: utf-8 -*-
"""
API export utility functions.
"""
import json
import os
import sys
from datetime import datetime

from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials  # noqa

from django.conf import settings
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

import six
from celery.backends.rpc import BacklogLimitExceeded
from celery.result import AsyncResult
from kombu.exceptions import OperationalError
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.reverse import reverse

try:
    from savReaderWriter import SPSSIOError
except ImportError:
    SPSSIOError = Exception

from onadata.apps.main.models import TokenStorageModel
from onadata.apps.viewer import tasks as viewer_task
from onadata.apps.viewer.models.export import Export, ExportConnectionError
from onadata.libs.exceptions import (
    J2XException,
    NoRecordsFoundError,
    NoRecordsPermission,
    ServiceUnavailable,
)
from onadata.libs.permissions import filter_queryset_xform_meta_perms_sql
from onadata.libs.utils import log
from onadata.libs.utils.async_status import (
    FAILED,
    PENDING,
    SUCCESSFUL,
    async_status,
    celery_state_to_status,
)
from onadata.libs.utils.common_tags import (
    DATAVIEW_EXPORT,
    GROUPNAME_REMOVED_FLAG,
    OSM,
    SUBMISSION_TIME,
)
from onadata.libs.utils.common_tools import report_exception
from onadata.libs.utils.export_tools import (
    check_pending_export,
    generate_attachments_zip_export,
    generate_export,
    generate_external_export,
    generate_geojson_export,
    generate_kml_export,
    generate_osm_export,
    newest_export_for,
    parse_request_export_options,
    should_create_new_export,
)
from onadata.libs.utils.google import create_flow
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name
from onadata.libs.utils.model_tools import get_columns_with_hxl
from onadata.settings.common import XLS_EXTENSIONS

# Supported external exports
EXTERNAL_EXPORT_TYPES = ["xlsx"]

EXPORT_EXT = {
    "xlsx": Export.XLSX_EXPORT,
    "csv": Export.CSV_EXPORT,
    "csvzip": Export.CSV_ZIP_EXPORT,
    "savzip": Export.SAV_ZIP_EXPORT,
    "uuid": Export.EXTERNAL_EXPORT,
    "kml": Export.KML_EXPORT,
    "zip": Export.ZIP_EXPORT,
    OSM: Export.OSM_EXPORT,
    "gsheets": Export.GOOGLE_SHEETS_EXPORT,
    "geojson": Export.GEOJSON_EXPORT,
}


def get_metadata_format(data_value):
    """Returns metadata format/extension"""
    fmt = "csv"

    if data_value.startswith("xform_geojson") or data_value.startswith(
        "dataview_geojson"
    ):
        fmt = "geojson"
    return fmt


def include_hxl_row(dv_columns, hxl_columns):
    """
    This function returns a boolean value. If the dataview's columns are not
    part of the hxl columns, we return False. Returning False would mean that
    we don't have to add the hxl column row if there aren't any hxl columns
    in the dataview.
    :param dv_columns - dataview columns
    :param hxl_columns - hxl columns from the dataview's xform

    :return True or False
    """
    return bool(set(hxl_columns).intersection(set(dv_columns)))


def _get_export_type(export_type):
    if export_type in list(EXPORT_EXT):
        export_type = EXPORT_EXT[export_type]
    else:
        raise exceptions.ParseError(
            _(f"'{export_type}' format not known or not implemented!")
        )

    return export_type


# pylint: disable=too-many-arguments, too-many-locals, too-many-branches
def custom_response_handler(  # noqa: C0901
    request,
    xform,
    query,
    export_type,
    token=None,
    meta=None,
    dataview=False,
    filename=None,
    metadata=None,
):
    """
    Returns a HTTP response with export file for download.
    """
    export_type = _get_export_type(export_type)
    if (
        export_type in EXTERNAL_EXPORT_TYPES
        and (token is not None)
        or (meta is not None)
    ):
        export_type = Export.EXTERNAL_EXPORT

    options = parse_request_export_options(request.query_params)

    dataview_pk = hasattr(dataview, "pk") and dataview.pk
    options["dataview_pk"] = dataview_pk

    if dataview:
        columns_with_hxl = get_columns_with_hxl(xform.survey.get("children"))

        if columns_with_hxl:
            options["include_hxl"] = include_hxl_row(
                dataview.columns, list(columns_with_hxl)
            )
    try:
        query = filter_queryset_xform_meta_perms_sql(xform, request.user, query)
    except NoRecordsPermission:
        return Response(
            data=json.dumps({"details": _("You don't have permission")}),
            status=status.HTTP_403_FORBIDDEN,
            content_type="application/json",
        )

    if query:
        options["query"] = query

    remove_group_name = options.get("remove_group_name")

    export_id = request.query_params.get("export_id")

    if export_id:
        export = get_object_or_404(Export, id=export_id, xform=xform)
    else:
        if export_type == Export.GOOGLE_SHEETS_EXPORT:

            return Response(
                data=json.dumps(
                    {"details": _("Sheets export only supported in async mode")}
                ),
                status=status.HTTP_403_FORBIDDEN,
                content_type="application/json",
            )

        # check if we need to re-generate,
        # we always re-generate if a filter is specified
        def _new_export():
            return _generate_new_export(
                request,
                xform,
                query,
                export_type,
                dataview_pk=dataview_pk,
                metadata=metadata,
            )

        if should_create_new_export(xform, export_type, options, request=request):
            export = _new_export()
        else:
            export = newest_export_for(xform, export_type, options)

            if not export.filename and not export.error_message:
                export = _new_export()

        log_export(request, xform, export_type)

        if export_type == Export.EXTERNAL_EXPORT:
            return external_export_response(export)

    if export.filename is None and export.error_message:
        raise exceptions.ParseError(export.error_message)

    # get extension from file_path, exporter could modify to
    # xlsx if it exceeds limits
    _path, ext = os.path.splitext(export.filename)
    ext = ext[1:]

    show_date = True
    if filename is None and export.status == Export.SUCCESSFUL:
        filename = _generate_filename(
            request, xform, remove_group_name, dataview_pk=dataview_pk
        )
    else:
        show_date = False
    response = response_with_mimetype_and_name(
        Export.EXPORT_MIMES[ext],
        filename,
        extension=ext,
        show_date=show_date,
        file_path=export.filepath,
    )

    return response


def _generate_new_export(  # noqa: C0901
    request, xform, query, export_type, dataview_pk=False, metadata=None
):
    query = _set_start_end_params(request, query)
    extension = _get_extension_from_export_type(export_type)

    options = {
        "extension": extension,
        "username": xform.user.username,
        "id_string": xform.id_string,
    }
    if query:
        options["query"] = query

    options["dataview_pk"] = dataview_pk
    if export_type == Export.GOOGLE_SHEETS_EXPORT:
        options["google_credentials"] = _get_google_credential(request).to_json()

    try:
        if export_type == Export.EXTERNAL_EXPORT:
            options["token"] = request.GET.get("token")
            options["data_id"] = request.GET.get("data_id")
            options["meta"] = request.GET.get("meta")

            export = generate_external_export(
                export_type,
                xform.user.username,
                xform.id_string,
                None,
                options,
                xform=xform,
            )
        elif export_type == Export.OSM_EXPORT:
            export = generate_osm_export(
                export_type,
                xform.user.username,
                xform.id_string,
                None,
                options,
                xform=xform,
            )
        elif export_type == Export.ZIP_EXPORT:
            export = generate_attachments_zip_export(
                export_type,
                xform.user.username,
                xform.id_string,
                None,
                options,
                xform=xform,
            )
        elif export_type == Export.KML_EXPORT:
            export = generate_kml_export(
                export_type,
                xform.user.username,
                xform.id_string,
                None,
                options,
                xform=xform,
            )
        elif export_type == Export.GEOJSON_EXPORT:
            export = generate_geojson_export(
                export_type,
                xform.user.username,
                xform.id_string,
                metadata,
                None,
                options,
                xform=xform,
            )
        else:
            options.update(parse_request_export_options(request.query_params))

            export = generate_export(export_type, xform, None, options)

        audit = {"xform": xform.id_string, "export_type": export_type}
        log.audit_log(
            log.Actions.EXPORT_CREATED,
            request.user,
            xform.user,
            _("Created %(export_type)s export on '%(id_string)s'.")
            % {"id_string": xform.id_string, "export_type": export_type.upper()},
            audit,
            request,
        )
    except NoRecordsFoundError as e:
        raise Http404(_("No records found to export")) from e
    except J2XException as e:
        # j2x exception
        return async_status(FAILED, str(e))
    except SPSSIOError as e:
        raise exceptions.ParseError(str(e)) from e
    else:
        return export


def log_export(request, xform, export_type):
    """
    Logs audit logs of export requests.
    """
    # log download as well
    audit = {"xform": xform.id_string, "export_type": export_type}
    log.audit_log(
        log.Actions.EXPORT_DOWNLOADED,
        request.user,
        xform.user,
        _(f"Downloaded {export_type.upper()} export on '{xform.id_string}'."),
        audit,
        request,
    )


def external_export_response(export):
    """
    Redirects to export_url of XLSReports successful export. In case of a
    failure, returns a 400 HTTP JSON response with the error message.
    """
    if isinstance(export, Export) and export.internal_status == Export.SUCCESSFUL:
        return HttpResponseRedirect(export.export_url)
    http_status = status.HTTP_400_BAD_REQUEST

    return Response(json.dumps(export), http_status, content_type="application/json")


def _generate_filename(request, xform, remove_group_name=False, dataview_pk=False):
    if request.GET.get("raw"):
        filename = None
    else:
        # append group name removed flag otherwise use the form id_string
        if remove_group_name:
            filename = f"{xform.id_string}-{GROUPNAME_REMOVED_FLAG}"
        elif dataview_pk:
            filename = f"{xform.id_string}-{DATAVIEW_EXPORT}"
        else:
            filename = xform.id_string

    return filename


def _set_start_end_params(request, query):
    # check for start and end params
    if "start" in request.GET or "end" in request.GET:
        query = json.loads(query) if isinstance(query, six.string_types) else query
        query[SUBMISSION_TIME] = {}

        try:
            if request.GET.get("start"):
                query[SUBMISSION_TIME]["$gte"] = _format_date_for_mongo(
                    request.GET["start"]
                )

            if request.GET.get("end"):
                query[SUBMISSION_TIME]["$lte"] = _format_date_for_mongo(
                    request.GET["end"]
                )
        except ValueError as e:
            raise exceptions.ParseError(
                _("Dates must be in the format YY_MM_DD_hh_mm_ss")
            ) from e
        else:
            query = json.dumps(query)

    return query


def _get_extension_from_export_type(export_type):
    extension = export_type

    if export_type == Export.XLSX_EXPORT:
        extension = "xlsx"
    elif export_type in [Export.CSV_ZIP_EXPORT, Export.SAV_ZIP_EXPORT]:
        extension = "zip"

    return extension


# pylint: disable=invalid-name
def _format_date_for_mongo(datetime_str):
    return datetime.strptime(datetime_str, "%y_%m_%d_%H_%M_%S").strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


def process_async_export(request, xform, export_type, options=None):
    """
    Check if should generate export or just return the latest export.
    Rules for regenerating an export are:
        1. Filter included on the exports.
        2. New submission done.
        3. Always regenerate external exports.
            (External exports uses templates and the template might have
             changed)
    :param request:
    :param xform:
    :param export_type:
    :param options: additional export params that may include
        query: export filter
        token: template url for xls external reports
        meta: metadataid that contains the external xls report template url
        remove_group_name: Flag to determine if group names should appear
    :return: response dictionary
    """
    # maintain the order of keys while processing the export

    export_type = _get_export_type(export_type)
    token = options.get("token")
    meta = options.get("meta")
    query = options.get("query")
    force_xlsx = options.get("force_xlsx")

    try:
        query = filter_queryset_xform_meta_perms_sql(xform, request.user, query)
    except NoRecordsPermission:
        payload = {"details": _("You don't have permission")}
        return Response(
            data=json.dumps(payload),
            status=status.HTTP_403_FORBIDDEN,
            content_type="application/json",
        )
    else:
        if query:
            options["query"] = query

    if (
        export_type in EXTERNAL_EXPORT_TYPES
        and (token is not None)
        or (meta is not None)
    ):
        export_type = Export.EXTERNAL_EXPORT

    if export_type == Export.GOOGLE_SHEETS_EXPORT:
        credential = _get_google_credential(request)

        if isinstance(credential, HttpResponseRedirect):
            return credential
        options["google_credentials"] = credential.to_json()

    if (
        should_create_new_export(xform, export_type, options, request=request)
        or export_type == Export.EXTERNAL_EXPORT
    ):
        resp = {
            "job_uuid": _create_export_async(
                xform, export_type, query, force_xlsx, options=options
            )
        }
    else:
        print("Do not create a new export.")
        export = newest_export_for(xform, export_type, options)

        if not export.filename:
            # tends to happen when using newest_export_for.
            resp = {
                "job_uuid": _create_export_async(
                    xform, export_type, query, force_xlsx, options=options
                )
            }
        else:
            resp = export_async_export_response(request, export)

    return resp


def _create_export_async(
    xform, export_type, query=None, force_xlsx=False, options=None
):
    """
    Creates async exports
    :param xform:
    :param export_type:
    :param query:
    :param force_xlsx:
    :param options:
    :return:
        job_uuid generated
    """
    export = check_pending_export(xform, export_type, options)

    if export:
        return export.task_id

    try:
        export, async_result = viewer_task.create_async_export(
            xform, export_type, query, force_xlsx, options=options
        )
    except ExportConnectionError as e:
        raise ServiceUnavailable from e

    return async_result.task_id


def export_async_export_response(request, export):
    """
    Checks the export status and generates the reponse
    :param request:
    :param export:
    :return: response dict example {"job_status": "Success", "export_url": ...}
    """
    if export.status == Export.SUCCESSFUL:
        if export.export_type not in [
            Export.EXTERNAL_EXPORT,
            Export.GOOGLE_SHEETS_EXPORT,
        ]:
            export_url = reverse(
                "export-detail", kwargs={"pk": export.pk}, request=request
            )
        else:
            export_url = export.export_url
        resp = async_status(SUCCESSFUL)
        resp["export_url"] = export_url
    elif export.status == Export.PENDING:
        resp = async_status(PENDING)
    else:
        resp = async_status(FAILED, export.error_message)

    return resp


def get_async_response(job_uuid, request, xform, count=0):
    """
    Returns the status of an async task for the given job_uuid.
    """

    def _get_response():
        export = get_object_or_404(Export, task_id=job_uuid)
        return export_async_export_response(request, export)

    try:
        job = AsyncResult(job_uuid)
        if job.state == "SUCCESS":
            resp = _get_response()
        else:
            resp = async_status(celery_state_to_status(job.state))

            # append task result to the response
            if job.result:
                result = job.result
                if isinstance(result, dict):
                    resp.update(result)
                else:
                    resp.update({"progress": str(result)})
    except (OperationalError, ConnectionError) as e:
        report_exception("Connection Error", e, sys.exc_info())
        if count > 0:
            raise ServiceUnavailable from e

        return get_async_response(job_uuid, request, xform, count + 1)
    except BacklogLimitExceeded:
        # most likely still processing
        resp = async_status(celery_state_to_status("PENDING"))

    return resp


# pylint: disable=redefined-builtin
def response_for_format(data, format=None):
    """
    Return appropriately formatted data in Response().
    """
    if format == "xml":
        formatted_data = data.xml
    elif format in ("xls", "xlsx"):
        if not data.xls or not data.xls.storage.exists(data.xls.name):
            raise Http404()

        formatted_data = data.xls
    else:
        formatted_data = (
            json.loads(data.json) if isinstance(data.json, str) else data.json
        )
    return Response(formatted_data)


def get_existing_file_format(data, format):
    """
    Util function to extract the existing form extension
    """
    if format in XLS_EXTENSIONS:
        existing_file_format = data.name.split(".")[-1]
        return existing_file_format
    return format


def generate_google_web_flow(request):
    """
    Returns a OAuth2WebServerFlow object from the request redirect_uri.
    """
    if "redirect_uri" in request.GET:
        redirect_uri = request.GET.get("redirect_uri")
    elif "redirect_uri" in request.POST:
        redirect_uri = request.POST.get("redirect_uri")
    elif "redirect_uri" in request.query_params:
        redirect_uri = request.query_params.get("redirect_uri")
    elif "redirect_uri" in request.data:
        redirect_uri = request.data.get("redirect_uri")
    else:
        redirect_uri = settings.GOOGLE_STEP2_URI
    return create_flow(redirect_uri)


def _get_google_credential(request):
    credential = None
    storage = None
    if request.user.is_authenticated:
        try:
            storage = TokenStorageModel.objects.get(id=request.user)
            credential = storage.credential
        except TokenStorageModel.DoesNotExist:
            pass
    elif request.session.get("access_token"):
        credential = Credentials(token=request.session["access_token"])

    if credential and not credential.valid:
        try:
            credential.refresh(Request())
            storage.credential = credential
            storage.save()
        except RefreshError:
            storage.delete()
            credential = None

    if not credential:
        google_flow = generate_google_web_flow(request)
        authorization_url, _state = google_flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        return HttpResponseRedirect(authorization_url)
    return credential
