# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""
data views.
"""

import os
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile
from time import strftime, strptime
from wsgiref.util import FileWrapper

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage, storages
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template import loader
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

import requests
from dict2xml import dict2xml
from dpath import util as dpath_util

try:
    from savReaderWriter import SPSSIOError
except ImportError:
    SPSSIOError = Exception

from onadata.apps.logger.models import Attachment
from onadata.apps.logger.views import download_jsonform
from onadata.apps.main.models import MetaData, TokenStorageModel, UserProfile
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.viewer.models.export import Export, ExportTypeError
from onadata.apps.viewer.tasks import create_async_export
from onadata.apps.viewer.xls_writer import XlsWriter
from onadata.libs.exceptions import NoRecordsFoundError
from onadata.libs.utils.chart_tools import build_chart_data
from onadata.libs.utils.common_tools import get_abbreviated_xpath, get_uuid
from onadata.libs.utils.export_tools import (
    DEFAULT_GROUP_DELIMITER,
    generate_export,
    kml_export_data,
    newest_export_for,
    should_create_new_export,
    str_to_bool,
)
from onadata.libs.utils.google_tools import create_flow
from onadata.libs.utils.image_tools import generate_media_download_url, image_url
from onadata.libs.utils.log import Actions, audit_log
from onadata.libs.utils.logger_tools import (
    generate_content_disposition_header,
    response_with_mimetype_and_name,
)
from onadata.libs.utils.user_auth import (
    get_xform_and_perms,
    has_permission,
    helper_auth_helper,
)
from onadata.libs.utils.viewer_tools import (
    create_attachments_zipfile,
    export_def_from_filename,
    get_form,
)

DEFAULT_REQUEST_TIMEOUT = getattr(settings, "DEFAULT_REQUEST_TIMEOUT", 30)

# pylint: disable=invalid-name
User = get_user_model()


def _get_start_end_submission_time(request):
    start = None
    end = None
    try:
        if request.GET.get("start"):
            start = datetime.strptime(
                request.GET["start"], "%y_%m_%d_%H_%M_%S"
            ).replace(tzinfo=timezone.utc)
        if request.GET.get("end"):
            end = datetime.strptime(request.GET["end"], "%y_%m_%d_%H_%M_%S").replace(
                tzinfo=timezone.utc
            )
    except ValueError:
        return HttpResponseBadRequest(
            _("Dates must be in the format YY_MM_DD_hh_mm_ss")
        )

    return start, end


def encode(time_str):
    """
    Reformat a time string into YYYY-MM-dd HH:mm:ss.
    """
    return strftime("%Y-%m-%d %H:%M:%S", strptime(time_str, "%Y_%m_%d_%H_%M_%S"))


def format_date_for_mongo(time_str):
    """
    Reformat a time string into YYYY-MM-ddTHH:mm:ss.
    """
    return datetime.strptime(time_str, "%y_%m_%d_%H_%M_%S").strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


def instances_for_export(data_dictionary, start=None, end=None):
    """
    Returns Instance submission queryset filtered by start and end dates.
    """
    kwargs = {}
    if start:
        kwargs["date_created__gte"] = start
    if end:
        kwargs["date_created__lte"] = end

    return data_dictionary.instances.filter(**kwargs)


def set_instances_for_export(id_string, owner, request):
    """
    Apply `start` and `end` filters to DataDictionary.instances_for_export.

    Returns True/False and DataDictionary/HttpResponseBadRequest if the process
    is successful or not respectively.
    """
    data_dictionary = get_object_or_404(
        DataDictionary, id_string__iexact=id_string, user=owner, deletd_at__isnull=True
    )
    start, end = request.GET.get("start"), request.GET.get("end")
    if start:
        try:
            start = encode(start)
        except ValueError:
            # bad format
            return [
                False,
                HttpResponseBadRequest(
                    _("Start time format must be YY_MM_DD_hh_mm_ss")
                ),
            ]
    if end:
        try:
            end = encode(end)
        except ValueError:
            # bad format
            return [
                False,
                HttpResponseBadRequest(_("End time format must be YY_MM_DD_hh_mm_ss")),
            ]
    if start or end:
        data_dictionary.instances_for_export = instances_for_export(
            data_dictionary, start, end
        )

    return [True, data_dictionary]


def average(values):
    """
    Get average of a list of values.
    """
    return sum(values, 0.0) / len(values) if values else None


def map_view(request, username, id_string, template="map.html"):
    """
    Map view.
    """
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form({"user": owner, "id_string__iexact": id_string})

    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_("Not shared."))
    data = {"content_user": owner, "xform": xform}
    data["profile"], __ = UserProfile.objects.get_or_create(user=owner)

    data["form_view"] = True
    data["jsonform_url"] = reverse(
        download_jsonform, kwargs={"username": username, "id_string": id_string}
    )
    data["enketo_edit_url"] = reverse(
        "edit_data", kwargs={"username": username, "id_string": id_string, "data_id": 0}
    )
    data["enketo_add_url"] = reverse(
        "enter_data", kwargs={"username": username, "id_string": id_string}
    )

    data["enketo_add_with_url"] = reverse(
        "add_submission_with", kwargs={"username": username, "id_string": id_string}
    )
    data["mongo_api_url"] = reverse(
        "mongo_view_api", kwargs={"username": username, "id_string": id_string}
    )
    data["delete_data_url"] = reverse(
        "delete_data", kwargs={"username": username, "id_string": id_string}
    )
    data["mapbox_layer"] = MetaData.mapbox_layer_upload(xform)
    audit = {"xform": xform.id_string}
    audit_log(
        Actions.FORM_MAP_VIEWED,
        request.user,
        owner,
        _(f"Requested map on '{xform.id_string}'."),
        audit,
        request,
    )
    return render(request, template, data)


def map_embed_view(request, username, id_string):
    """
    Embeded map view.
    """
    return map_view(request, username, id_string, template="map_embed.html")


def add_submission_with(request, username, id_string):
    """
    Returns JSON response with Enketo form url preloaded with coordinates.
    """

    def geopoint_xpaths(username, id_string):
        """
        Returns xpaths with elements of type 'geopoint'.
        """
        data_dictionary = DataDictionary.objects.get(
            user__username__iexact=username, id_string__iexact=id_string
        )
        return [
            get_abbreviated_xpath(e.get_xpath())
            for e in data_dictionary.get_survey_elements()
            if e.bind.get("type") == "geopoint"
        ]

    value = request.GET.get("coordinates")
    xpaths = geopoint_xpaths(username, id_string)
    xml_dict = {}
    for path in xpaths:
        dpath_util.new(xml_dict, path, value)

    context = {
        "username": username,
        "id_string": id_string,
        "xml_content": dict2xml(xml_dict),
    }
    instance_xml = loader.get_template("instance_add.xml").render(context)

    url = settings.ENKETO_API_INSTANCE_IFRAME_URL
    return_url = reverse(
        "thank_you_submission", kwargs={"username": username, "id_string": id_string}
    )
    if settings.DEBUG:
        openrosa_url = f"https://dev.formhub.org/{username}"
    else:
        openrosa_url = request.build_absolute_uri(f"/{username}")
    payload = {
        "return_url": return_url,
        "form_id": id_string,
        "server_url": openrosa_url,
        "instance": instance_xml,
        "instance_id": get_uuid(),
    }

    response = requests.post(
        url,
        data=payload,
        auth=(settings.ENKETO_API_TOKEN, ""),
        timeout=DEFAULT_REQUEST_TIMEOUT,
        verify=getattr(settings, "VERIFY_SSL", True),
    )

    # pylint: disable=http-response-with-content-type-json
    return HttpResponse(response.text, content_type="application/json")


# pylint: disable=unused-argument
def thank_you_submission(request, username, id_string):
    """
    Thank you view after successful submission.
    """
    return HttpResponse("Thank You")


# pylint: disable=too-many-locals
def data_export(request, username, id_string, export_type):  # noqa C901
    """
    Data export view.
    """
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form({"user": owner, "id_string__iexact": id_string})
    id_string = xform.id_string

    helper_auth_helper(request)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_("Not shared."))
    query = request.GET.get("query")
    extension = export_type

    # check if we should force xlsx
    if export_type == Export.XLSX_EXPORT:
        extension = "xlsx"
    elif export_type in [Export.CSV_ZIP_EXPORT, Export.SAV_ZIP_EXPORT]:
        extension = "zip"

    audit = {"xform": xform.id_string, "export_type": export_type}

    options = {
        "extension": extension,
        "username": username,
        "id_string": id_string,
        "host": request.get_host(),
    }
    if query:
        options["query"] = query

    # check if we need to re-generate,
    # we always re-generate if a filter is specified
    if (
        should_create_new_export(xform, export_type, options)
        or query
        or "start" in request.GET
        or "end" in request.GET
    ):
        # check for start and end params
        start, end = _get_start_end_submission_time(request)
        options.update({"start": start, "end": end})

        # pylint: disable=broad-except
        try:
            export = generate_export(export_type, xform, None, options)
            audit_log(
                Actions.EXPORT_CREATED,
                request.user,
                owner,
                _(f"Created {export_type.upper()} export on '{id_string}'."),
                audit,
                request,
            )
        except NoRecordsFoundError:
            return HttpResponseNotFound(_("No records found to export"))
        except SPSSIOError as e:
            return HttpResponseBadRequest(str(e))
    else:
        export = newest_export_for(xform, export_type, options)

    # log download as well
    audit_log(
        Actions.EXPORT_DOWNLOADED,
        request.user,
        owner,
        _(f"Downloaded {export_type.upper()} export on '{id_string}'."),
        audit,
        request,
    )

    if not export.filename and not export.error_message:
        # tends to happen when using newset_export_for.
        return HttpResponseNotFound("File does not exist!")
    if not export.filename and export.error_message:
        return HttpResponseBadRequest(str(export.error_message))

    # get extension from file_path, exporter could modify to
    # xlsx if it exceeds limits
    __, extension = os.path.splitext(export.filename)
    extension = extension[1:]
    if request.GET.get("raw"):
        id_string = None

    response = response_with_mimetype_and_name(
        Export.EXPORT_MIMES[extension],
        id_string,
        extension=extension,
        file_path=export.filepath,
    )

    return response


# pylint: disable=too-many-locals
@login_required
@require_POST
def create_export(request, username, id_string, export_type):
    """
    Create async export tasks view.
    """
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form({"user": owner, "id_string__iexact": id_string})

    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_("Not shared."))

    if export_type == Export.EXTERNAL_EXPORT:
        # check for template before trying to generate a report
        if not MetaData.external_export(xform):
            return HttpResponseForbidden(_("No XLS Template set."))

    credential = None
    if export_type == Export.GOOGLE_SHEETS_EXPORT:
        credential = _get_google_credential(request)
        if isinstance(credential, HttpResponseRedirect):
            return credential

    query = request.POST.get("query")
    force_xlsx = request.POST.get("xls") != "true"

    # export options
    group_delimiter = request.POST.get("options[group_delimiter]", "/")
    if group_delimiter not in [".", "/"]:
        return HttpResponseBadRequest(_(f"{group_delimiter} is not a valid delimiter"))

    # default is True, so when dont_.. is yes
    # split_select_multiples becomes False
    split_select_multiples = (
        request.POST.get("options[dont_split_select_multiples]", "no") == "no"
    )

    binary_select_multiples = getattr(settings, "BINARY_SELECT_MULTIPLES", False)
    remove_group_name = request.POST.get("options[remove_group_name]", "false")
    value_select_multiples = request.POST.get(
        "options[value_select_multiples]", "false"
    )

    # external export option
    meta = request.POST.get("meta")
    options = {
        "group_delimiter": group_delimiter,
        "split_select_multiples": split_select_multiples,
        "binary_select_multiples": binary_select_multiples,
        "value_select_multiples": str_to_bool(value_select_multiples),
        "remove_group_name": str_to_bool(remove_group_name),
        "meta": meta.replace(",", "") if meta else None,
        "google_credentials": credential,
        "host": request.get_host(),
    }

    try:
        create_async_export(xform, export_type, query, force_xlsx, options)
    except ExportTypeError:
        return HttpResponseBadRequest(_(f"{export_type} is not a valid export type"))

    audit = {"xform": xform.id_string, "export_type": export_type}
    id_string = xform.id_string
    audit_log(
        Actions.EXPORT_CREATED,
        request.user,
        owner,
        _(f"Created {export_type.upper()} export on '{id_string}'."),
        audit,
        request,
    )
    return HttpResponseRedirect(
        reverse(
            export_list,
            kwargs={
                "username": username,
                "id_string": id_string,
                "export_type": export_type,
            },
        )
    )


def _get_google_credential(request):
    google_flow = create_flow()
    return HttpResponseRedirect(
        google_flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
    )


def export_list(request, username, id_string, export_type):  # noqa C901
    """
    Export list view.
    """
    credential = None

    if export_type not in Export.EXPORT_TYPE_DICT:
        return HttpResponseBadRequest(
            _(f'Export type "{export_type}" is not supported.')
        )

    if export_type == Export.GOOGLE_SHEETS_EXPORT:
        # Retrieve  google creds or redirect to google authorization page
        credential = _get_google_credential(request)
        if isinstance(credential, HttpResponseRedirect):
            return credential
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form({"user": owner, "id_string__iexact": id_string})

    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_("Not shared."))

    if export_type == Export.EXTERNAL_EXPORT:
        # check for template before trying to generate a report
        if not MetaData.external_export(xform):
            return HttpResponseForbidden(_("No XLS Template set."))
    # Get meta and token
    export_token = request.GET.get("token")
    export_meta = request.GET.get("meta")
    options = {
        "group_delimiter": DEFAULT_GROUP_DELIMITER,
        "remove_group_name": False,
        "split_select_multiples": True,
        "binary_select_multiples": False,
        "meta": export_meta,
        "token": export_token,
        "google_credentials": credential,
        "host": request.get_host(),
    }

    if should_create_new_export(xform, export_type, options):
        try:
            create_async_export(
                xform, export_type, query=None, force_xlsx=True, options=options
            )
        except ExportTypeError:
            return HttpResponseBadRequest(
                _(f"{export_type} is not a valid export type")
            )

    metadata_qs = MetaData.objects.filter(
        object_id=xform.id, data_type="external_export"
    ).values("id", "data_value")

    for metadata in metadata_qs:
        metadata["data_value"] = metadata.get("data_value").split("|")[0]

    data = {
        "username": owner.username,
        "xform": xform,
        "export_type": export_type,
        "export_type_name": Export.EXPORT_TYPE_DICT[export_type],
        "exports": Export.objects.filter(xform=xform, export_type=export_type).order_by(
            "-created_on"
        ),
        "metas": metadata_qs,
    }  # yapf: disable

    return render(request, "export_list.html", data)


def export_progress(request, username, id_string, export_type):
    """
    Async export progress view.
    """
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form({"user": owner, "id_string__iexact": id_string})

    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_("Not shared."))

    # find the export entry in the db
    export_ids = request.GET.getlist("export_ids")
    exports = Export.objects.filter(
        xform=xform, id__in=export_ids, export_type=export_type
    )
    statuses = []
    for export in exports:
        status = {
            "complete": False,
            "url": None,
            "filename": None,
            "export_id": export.id,
        }

        if export.status == Export.SUCCESSFUL:
            status["url"] = reverse(
                export_download,
                kwargs={
                    "username": owner.username,
                    "id_string": xform.id_string,
                    "export_type": export.export_type,
                    "filename": export.filename,
                },
            )
            status["filename"] = export.filename
            if (
                export.export_type == Export.GOOGLE_SHEETS_EXPORT
                and export.export_url is None
            ):
                status["url"] = None
            if (
                export.export_type == Export.EXTERNAL_EXPORT
                and export.export_url is None
            ):
                status["url"] = None
        # mark as complete if it either failed or succeeded but NOT pending
        if export.status in [Export.SUCCESSFUL, Export.FAILED]:
            status["complete"] = True
        statuses.append(status)

    return JsonResponse(statuses, safe=False)


def export_download(request, username, id_string, export_type, filename):
    """
    Export download view.
    """
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form({"user": owner, "id_string__iexact": id_string})

    helper_auth_helper(request)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_("Not shared."))

    # find the export entry in the db
    export = get_object_or_404(Export, xform=xform, filename=filename)

    is_external_export = export_type in [
        Export.GOOGLE_SHEETS_EXPORT,
        Export.EXTERNAL_EXPORT,
    ]
    if is_external_export and export.export_url is not None:
        return HttpResponseRedirect(export.export_url)

    ext, mime_type = export_def_from_filename(export.filename)
    export_type = export.export_type
    filename = export.filename
    id_string = xform.id_string

    audit = {"xform": xform.id_string, "export_type": export.export_type}
    audit_log(
        Actions.EXPORT_DOWNLOADED,
        request.user,
        owner,
        _(f"Downloaded {export_type.upper()} export '{filename}' on '{id_string}'."),
        audit,
        request,
    )
    if request.GET.get("raw"):
        id_string = None

    default_storage = storages["default"]
    if not isinstance(default_storage, FileSystemStorage):
        return HttpResponseRedirect(default_storage.url(export.filepath))
    basename = os.path.splitext(export.filename)[0]
    response = response_with_mimetype_and_name(
        mime_type,
        name=basename,
        extension=ext,
        file_path=export.filepath,
        show_date=False,
    )
    return response


@login_required
@require_POST
def delete_export(request, username, id_string, export_type):
    """
    Delete export view.
    """
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form({"user": owner, "id_string__iexact": id_string})

    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_("Not shared."))

    export_id = request.POST.get("export_id")

    # find the export entry in the db
    export = get_object_or_404(Export, id=export_id)
    export_type = export.export_type
    export.delete()

    filename = export.filename
    id_string = xform.id_string
    audit = {"xform": xform.id_string, "export_type": export.export_type}
    audit_log(
        Actions.EXPORT_DOWNLOADED,
        request.user,
        owner,
        _(f"Deleted {export_type.upper()} export '{filename}' on '{id_string}'."),
        audit,
        request,
    )
    return HttpResponseRedirect(
        reverse(
            export_list,
            kwargs={
                "username": username,
                "id_string": id_string,
                "export_type": export_type,
            },
        )
    )


def zip_export(request, username, id_string):
    """
    Zip export view.
    """
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form({"user": owner, "id_string__iexact": id_string})

    helper_auth_helper(request)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_("Not shared."))
    if request.GET.get("raw"):
        id_string = None

    attachments = Attachment.objects.filter(instance__xform=xform)
    zip_file = None

    with NamedTemporaryFile() as zip_file:
        create_attachments_zipfile(attachments, zip_file)
        audit = {"xform": xform.id_string, "export_type": Export.ZIP_EXPORT}
        audit_log(
            Actions.EXPORT_CREATED,
            request.user,
            owner,
            _(f"Created ZIP export on '{xform.id_string}'."),
            audit,
            request,
        )
        # log download as well
        audit_log(
            Actions.EXPORT_DOWNLOADED,
            request.user,
            owner,
            _(f"Downloaded ZIP export on '{xform.id_string}'."),
            audit,
            request,
        )
        if request.GET.get("raw"):
            id_string = None

        response = response_with_mimetype_and_name("zip", id_string)
        response.write(FileWrapper(zip_file))
        response["Content-Length"] = zip_file.tell()
        zip_file.seek(0)

    return response


def kml_export(request, username, id_string):
    """
    KML export view.
    """
    # read the locations from the database
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form({"user": owner, "id_string__iexact": id_string})

    helper_auth_helper(request)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_("Not shared."))
    data = {"data": kml_export_data(id_string, user=owner, xform=xform)}
    response = render(
        request, "survey.kml", data, content_type="application/vnd.google-earth.kml+xml"
    )
    response["Content-Disposition"] = generate_content_disposition_header(
        id_string, "kml"
    )
    audit = {"xform": xform.id_string, "export_type": Export.KML_EXPORT}
    audit_log(
        Actions.EXPORT_CREATED,
        request.user,
        owner,
        _(f"Created KML export on '{xform.id_string}'."),
        audit,
        request,
    )
    # log download as well
    audit_log(
        Actions.EXPORT_DOWNLOADED,
        request.user,
        owner,
        _(f"Downloaded KML export on '{xform.id_string}'."),
        audit,
        request,
    )

    return response


def google_xlsx_export(request, username, id_string):
    """
    Google export view, uploads an excel export to google drive and then
    redirects to the uploaded google sheet.
    """
    token = None
    if request.user.is_authenticated:
        try:
            token_storage = TokenStorageModel.objects.get(id=request.user)
        except TokenStorageModel.DoesNotExist:
            pass
        else:
            token = token_storage.token
    elif request.session.get("access_token"):
        token = request.session.get("access_token")

    if token is None:
        request.session["google_redirect_url"] = reverse(
            google_xlsx_export, kwargs={"username": username, "id_string": id_string}
        )
        google_flow = create_flow()
        return HttpResponseRedirect(
            google_flow.authorization_url(
                access_type="offline", include_granted_scopes="true", prompt="consent"
            )
        )

    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form({"user": owner, "id_string__iexact": id_string})

    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_("Not shared."))

    is_valid, data_dictionary = set_instances_for_export(id_string, owner, request)
    if not is_valid:
        return data_dictionary

    xls_writer = XlsWriter()
    with NamedTemporaryFile(delete=False) as tmp:
        xls_writer.set_file(tmp)
        xls_writer.set_data_dictionary(data_dictionary)
        temp_file = xls_writer.save_workbook_to_file()
        temp_file.close()
    url = None
    os.unlink(tmp.name)
    audit = {"xform": xform.id_string, "export_type": "google"}
    audit_log(
        Actions.EXPORT_CREATED,
        request.user,
        owner,
        _(f"Created Google Docs export on '{xform.id_string}'."),
        audit,
        request,
    )

    return HttpResponseRedirect(url)


def data_view(request, username, id_string):
    """
    Data view displays submission data.
    """
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form({"id_string__iexact": id_string, "user": owner})
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_("Not shared."))

    data = {"owner": owner, "xform": xform}
    audit = {
        "xform": xform.id_string,
    }
    audit_log(
        Actions.FORM_DATA_VIEWED,
        request.user,
        owner,
        _(f"Requested data view for '{xform.id_string}'."),
        audit,
        request,
    )

    return render(request, "data_view.html", data)


def attachment_url(request, size="medium"):
    """
    Redirects to image attachment  of the specified size, defaults to 'medium'.
    """
    media_file = request.GET.get("media_file")
    no_redirect = request.GET.get("no_redirect")
    attachment_id = request.GET.get("attachment_id")

    if not media_file and not attachment_id:
        return HttpResponseNotFound(_("Attachment not found"))
    if attachment_id:
        attachment = get_object_or_404(Attachment, pk=attachment_id)
    else:
        result = Attachment.objects.filter(media_file=media_file).order_by()[0:1]
        if not result:
            return HttpResponseNotFound(_("Attachment not found"))
        attachment = result[0]

    if size == "original" and no_redirect == "true":
        response = response_with_mimetype_and_name(
            attachment.mimetype,
            attachment.name,
            extension=attachment.extension,
            file_path=attachment.media_file.name,
        )

        return response
    if not attachment.mimetype.startswith("image"):
        return generate_media_download_url(attachment)
    media_url = image_url(attachment, size)
    if media_url:
        return redirect(media_url)

    return HttpResponseNotFound(_("Error: Attachment not found"))


def instance(request, username, id_string):
    """
    Data view for browsing submissions one at a time.
    """
    xform, _is_owner, can_edit, can_view = get_xform_and_perms(
        username, id_string, request
    )
    # no access
    if not (
        xform.shared_data
        or can_view
        or request.session.get("public_link") == xform.uuid
    ):
        return HttpResponseForbidden(_("Not shared."))

    audit = {
        "xform": xform.id_string,
    }
    audit_log(
        Actions.FORM_DATA_VIEWED,
        request.user,
        xform.user,
        _(f"Requested instance view for '{xform.id_string}'."),
        audit,
        request,
    )

    return render(
        request,
        "instance.html",
        {
            "username": username,
            "id_string": id_string,
            "xform": xform,
            "can_edit": can_edit,
        },
    )


def charts(request, username, id_string):
    """
    Charts view.
    """
    xform, _is_owner, _can_edit, can_view = get_xform_and_perms(
        username, id_string, request
    )

    # no access
    if not (
        xform.shared_data
        or can_view
        or request.session.get("public_link") == xform.uuid
    ):
        return HttpResponseForbidden(_("Not shared."))

    try:
        lang_index = int(request.GET.get("lang", 0))
    except ValueError:
        lang_index = 0

    try:
        page = int(request.GET.get("page", 0))
    except ValueError:
        page = 0
    else:
        page = max(page - 1, 0)

    summaries = build_chart_data(xform, lang_index, page)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        template = "charts_snippet.html"
    else:
        template = "charts.html"

    return render(
        request, template, {"xform": xform, "summaries": summaries, "page": page + 1}
    )


def stats_tables(request, username, id_string):
    """
    Stats view.
    """
    xform, _is_owner, _can_edit, can_view = get_xform_and_perms(
        username, id_string, request
    )
    # no access
    if not (
        xform.shared_data
        or can_view
        or request.session.get("public_link") == xform.uuid
    ):
        return HttpResponseForbidden(_("Not shared."))

    return render(request, "stats_tables.html", {"xform": xform})
