# -*- coding: utf-8 -*-
"""
logger views.
"""
import os
import tempfile

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.core.files.storage import storages
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.template import RequestContext, loader
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

import six
from django_digest import HttpDigestAuthenticator

from onadata.apps.api.tools import get_host_domain
from onadata.apps.logger.import_tools import import_instances_from_zip
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.models import MetaData, UserProfile
from onadata.libs.exceptions import EnketoError
from onadata.libs.utils.cache_tools import USER_PROFILE_PREFIX, cache
from onadata.libs.utils.decorators import is_owner
from onadata.libs.utils.log import Actions, audit_log
from onadata.libs.utils.logger_tools import (
    BaseOpenRosaResponse,
    OpenRosaResponse,
    OpenRosaResponseBadRequest,
    PublishXForm,
    inject_instanceid,
    publish_form,
    response_with_mimetype_and_name,
    safe_create_instance,
)
from onadata.libs.utils.user_auth import (
    HttpResponseNotAuthorized,
    add_cors_headers,
    has_edit_permission,
    has_permission,
    helper_auth_helper,
)
from onadata.libs.utils.viewer_tools import get_enketo_urls, get_form, get_form_url

IO_ERROR_STRINGS = ["request data read error", "error during read(65536) on wsgi.input"]

# pylint: disable=invalid-name
User = get_user_model()


def _bad_request(e):
    strerror = str(e)

    return strerror and strerror in IO_ERROR_STRINGS


def _extract_uuid(input_string):
    key_index = input_string.find("@key=")
    input_string = input_string[key_index:-1].replace("@key=", "")
    if input_string.startswith("uuid:"):
        input_string = input_string.replace("uuid:", "")
    return input_string


def _parse_int(num):
    try:
        return num and int(num)
    except ValueError:
        pass
    return None


def _html_submission_response(request, instance):
    data = {}
    data["username"] = instance.xform.user.username
    data["id_string"] = instance.xform.id_string
    data["domain"] = get_host_domain(request)

    return render(request, "submission.html", data)


def _submission_response(instance):
    data = {}
    data["message"] = _("Successful submission.")
    data["formid"] = instance.xform.id_string
    data["encrypted"] = instance.xform.encrypted
    data["instanceID"] = f"uuid:{instance.uuid}"
    data["submissionDate"] = instance.date_created.isoformat()
    data["markedAsCompleteDate"] = instance.date_modified.isoformat()

    return BaseOpenRosaResponse(loader.get_template("submission.xml").render(data))


@require_POST
@csrf_exempt
def bulksubmission(request, username):
    """
    Bulk submission view.
    """
    # puts it in a temp directory.
    # runs "import_tools(temp_directory)"
    # deletes
    posting_user = get_object_or_404(User, username__iexact=username)

    # request.FILES is a django.utils.datastructures.MultiValueDict
    # for each key we have a list of values
    try:
        temp_postfile = request.FILES.pop("zip_submission_file", [])
    except IOError:
        return HttpResponseBadRequest(
            _(
                "There was a problem receiving your "
                "ODK submission. [Error: IO Error "
                "reading data]"
            )
        )
    if len(temp_postfile) != 1:
        return HttpResponseBadRequest(
            _(
                "There was a problem receiving your"
                " ODK submission. [Error: multiple "
                "submission files (?)]"
            )
        )

    postfile = temp_postfile[0]
    tempdir = tempfile.gettempdir()
    our_tfpath = os.path.join(tempdir, postfile.name)

    with open(our_tfpath, "wb") as f:
        f.write(postfile.read())

    with open(our_tfpath, "rb") as f:
        total_count, success_count, errors = import_instances_from_zip(f, posting_user)
    # chose the try approach as suggested by the link below
    # http://stackoverflow.com/questions/82831
    try:
        os.remove(our_tfpath)
    except IOError:
        pass
    json_msg = {
        "message": _(
            "Submission complete. Out of %(total)d "
            "survey instances, %(success)d were imported, "
            "(%(rejected)d were rejected as duplicates, "
            "missing forms, etc.)"
        )
        % {
            "total": total_count,
            "success": success_count,
            "rejected": total_count - success_count,
        },
        "errors": f"{len(errors)} {errors}",
    }
    audit = {"bulk_submission_log": json_msg}
    audit_log(
        Actions.USER_BULK_SUBMISSION,
        request.user,
        posting_user,
        _("Made bulk submissions."),
        audit,
        request,
    )
    response = JsonResponse(json_msg)
    response.status_code = 200
    response["Location"] = request.build_absolute_uri(request.path)
    return response


@login_required
def bulksubmission_form(request, username=None):
    """
    Bulk submission form view
    """
    username = username if username is None else username
    if request.user.username == username:
        return render(request, "bulk_submission_form.html")

    return HttpResponseRedirect(f"/{request.user.username}")


# pylint: disable=invalid-name
@require_GET
def formList(request, username):  # noqa N802
    """
    formList view, /formList OpenRosa Form Discovery API 1.0.
    """
    formlist_user = get_object_or_404(User, username__iexact=username)
    profile = cache.get(f"{USER_PROFILE_PREFIX}{formlist_user.username}")
    if not profile:
        profile, __ = UserProfile.objects.get_or_create(
            user__username=formlist_user.username
        )

    if profile.require_auth:
        authenticator = HttpDigestAuthenticator()
        if not authenticator.authenticate(request):
            return authenticator.build_challenge_response()

        # unauthorized if user in auth request does not match user in path
        # unauthorized if user not active
        if not request.user.is_active:
            return HttpResponseNotAuthorized()

    # filter private forms (where require_auth=False)
    # for users who are non-owner
    if request.user.username == profile.user.username:
        xforms = XForm.objects.filter(
            downloadable=True, deleted_at__isnull=True, user__username__iexact=username
        )
    else:
        xforms = XForm.objects.filter(
            downloadable=True,
            deleted_at__isnull=True,
            user__username__iexact=username,
            require_auth=False,
        )

    audit = {}
    audit_log(
        Actions.USER_FORMLIST_REQUESTED,
        request.user,
        formlist_user,
        _("Requested forms list."),
        audit,
        request,
    )

    data = {
        "host": request.build_absolute_uri().replace(request.get_full_path(), ""),
        "xforms": xforms,
    }
    response = render(
        request, "xformsList.xml", data, content_type="text/xml; charset=utf-8"
    )
    response["X-OpenRosa-Version"] = "1.0"
    response["Date"] = timezone.localtime().strftime("%a, %d %b %Y %H:%M:%S %Z")

    return response


# pylint: disable=invalid-name
@require_GET
def xformsManifest(request, username, id_string):  # noqa N802
    """
    XFormManifest view, part of OpenRosa Form Discovery API 1.0.
    """
    xform_kwargs = {"id_string__iexact": id_string, "user__username__iexact": username}

    xform = get_form(xform_kwargs)
    formlist_user = xform.user
    profile = cache.get(f"{USER_PROFILE_PREFIX}{formlist_user.username}")
    if not profile:
        profile, __ = UserProfile.objects.get_or_create(
            user__username=formlist_user.username
        )

    if profile.require_auth:
        authenticator = HttpDigestAuthenticator()
        if not authenticator.authenticate(request):
            return authenticator.build_challenge_response()

    response = render(
        request,
        "xformsManifest.xml",
        {
            "host": request.build_absolute_uri().replace(request.get_full_path(), ""),
            "media_files": MetaData.media_upload(xform, download=True),
        },
        content_type="text/xml; charset=utf-8",
    )
    response["X-OpenRosa-Version"] = "1.0"
    response["Date"] = timezone.localtime().strftime("%a, %d %b %Y %H:%M:%S %Z")

    return response


# pylint: disable=too-many-return-statements
# pylint: disable=too-many-branches
@require_http_methods(["HEAD", "POST"])
@csrf_exempt
def submission(request, username=None):  # noqa C901
    """
    Submission view, /submission of the OpenRosa Form Submission API 1.0.
    """
    if username:
        formlist_user = get_object_or_404(User, username__iexact=username)
        profile, __ = UserProfile.objects.get_or_create(user=formlist_user)

        if profile.require_auth:
            authenticator = HttpDigestAuthenticator()
            if not authenticator.authenticate(request):
                return authenticator.build_challenge_response()

    if request.method == "HEAD":
        response = OpenRosaResponse(status=204)
        if username:
            response["Location"] = request.build_absolute_uri().replace(
                request.get_full_path(), f"/{username}/submission"
            )
        else:
            response["Location"] = request.build_absolute_uri().replace(
                request.get_full_path(), "/submission"
            )
        return response

    xml_file_list = []
    media_files = []

    # request.FILES is a django.utils.datastructures.MultiValueDict
    # for each key we have a list of values
    try:
        xml_file_list = request.FILES.pop("xml_submission_file", [])
        if len(xml_file_list) != 1:
            return OpenRosaResponseBadRequest(
                _("There should be a single XML submission file.")
            )
        # save this XML file and media files as attachments
        media_files = request.FILES.values()

        # get uuid from post request
        uuid = request.POST.get("uuid")

        error, instance = safe_create_instance(
            username, xml_file_list[0], media_files, uuid, request
        )

        if error:
            return error
        if instance is None:
            return OpenRosaResponseBadRequest(_("Unable to create submission."))

        audit = {"xform": instance.xform.id_string}
        audit_log(
            Actions.SUBMISSION_CREATED,
            request.user,
            instance.xform.user,
            _("Created submission on form %(id_string)s.")
            % {"id_string": instance.xform.id_string},
            audit,
            request,
        )

        # response as html if posting with a UUID
        if not username and uuid:
            response = _html_submission_response(request, instance)
        else:
            response = _submission_response(instance)

        # ODK needs two things for a form to be considered successful
        # 1) the status code needs to be 201 (created)
        # 2) The location header needs to be set to the host it posted to
        response.status_code = 201
        response["Location"] = request.build_absolute_uri(request.path)
        return response
    except IOError as e:
        if _bad_request(e):
            return OpenRosaResponseBadRequest(_("File transfer interruption."))
        raise
    finally:
        if xml_file_list:
            for _file in xml_file_list:
                _file.close()
        if media_files:
            for _file in media_files:
                _file.close()


def download_xform(request, username, id_string):
    """
    Download XForm XML view.
    """
    user = get_object_or_404(User, username__iexact=username)
    xform = get_form({"user": user, "id_string__iexact": id_string})
    profile, __ = UserProfile.objects.get_or_create(user=user)

    if profile.require_auth:
        authenticator = HttpDigestAuthenticator()
        if not authenticator.authenticate(request):
            return authenticator.build_challenge_response()
    audit = {"xform": xform.id_string}
    audit_log(
        Actions.FORM_XML_DOWNLOADED,
        request.user,
        xform.user,
        _("Downloaded XML for form '%(id_string)s'.") % {"id_string": xform.id_string},
        audit,
        request,
    )
    response = response_with_mimetype_and_name("xml", id_string, show_date=False)
    response.content = xform.xml
    return response


def download_xlsform(request, username, id_string):
    """
    Download XLSForm view.
    """
    xform = get_form(
        {"user__username__iexact": username, "id_string__iexact": id_string}
    )
    owner = User.objects.get(username__iexact=username)

    helper_auth_helper(request)

    if not has_permission(xform, owner, request, xform.shared):
        return HttpResponseForbidden("Not shared.")

    file_path = xform.xls.name
    default_storage = storages["default"]

    if file_path != "" and default_storage.exists(file_path):
        audit = {"xform": xform.id_string}
        audit_log(
            Actions.FORM_XLS_DOWNLOADED,
            request.user,
            xform.user,
            _("Downloaded XLS file for form '%(id_string)s'.")
            % {"id_string": xform.id_string},
            audit,
            request,
        )
        split_path = file_path.split(os.extsep)
        extension = "xls"

        if len(split_path) > 1:
            extension = split_path[len(split_path) - 1]

        response = response_with_mimetype_and_name(
            "vnd.ms-excel",
            id_string,
            show_date=False,
            extension=extension,
            file_path=file_path,
        )

        return response

    messages.add_message(
        request,
        messages.WARNING,
        _("No XLS file for your form <strong>%(id)s</strong>") % {"id": id_string},
    )

    return HttpResponseRedirect(f"/{username}")


def download_jsonform(request, username, id_string):
    """
    XForm JSON view.
    """
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form(
        {"user__username__iexact": username, "id_string__iexact": id_string}
    )

    if request.method == "OPTIONS":
        response = HttpResponse()
        add_cors_headers(response)
        return response
    helper_auth_helper(request)
    if not has_permission(xform, owner, request, xform.shared):
        response = HttpResponseForbidden(_("Not shared."))
        add_cors_headers(response)
        return response
    response = response_with_mimetype_and_name("json", id_string, show_date=False)
    if "callback" in request.GET and request.GET.get("callback") != "":
        callback = request.GET.get("callback")
        response.content = f"{callback}({xform.json})"
    else:
        add_cors_headers(response)
        response.content = xform.json
    return response


@is_owner
@require_POST
def delete_xform(request, username, id_string):
    """
    Delete XForm view.
    """
    xform = get_form(
        {"user__username__iexact": username, "id_string__iexact": id_string}
    )

    # Delete xform
    xform.soft_delete(user=request.user)

    audit = {}
    audit_log(
        Actions.FORM_DELETED,
        request.user,
        xform.user,
        _("Deleted form '%(id_string)s'.")
        % {
            "id_string": xform.id_string,
        },
        audit,
        request,
    )
    return HttpResponseRedirect("/")


@is_owner
def toggle_downloadable(request, username, id_string):
    """
    Toggle XForm view, changes downloadable status of a form.
    """
    xform = get_form(
        {"user__username__iexact": username, "id_string__iexact": id_string}
    )
    xform.downloadable = not xform.downloadable
    xform.save()
    audit = {}
    audit_log(
        Actions.FORM_UPDATED,
        request.user,
        xform.user,
        _("Made form '%(id_string)s' %(downloadable)s.")
        % {
            "id_string": xform.id_string,
            "downloadable": (
                _("downloadable") if xform.downloadable else _("un-downloadable")
            ),
        },
        audit,
        request,
    )
    return HttpResponseRedirect(f"/{username}")


def enter_data(request, username, id_string):
    """
    Redirects to Enketo webform view.
    """
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_form(
        {"user__username__iexact": username, "id_string__iexact": id_string}
    )

    if not has_edit_permission(xform, owner, request, xform.shared):
        return HttpResponseForbidden(_("Not shared."))

    form_url = get_form_url(request, username, settings.ENKETO_PROTOCOL)

    try:
        enketo_urls = get_enketo_urls(form_url, xform.id_string)
        url = enketo_urls.get("url")
        if not url:
            return HttpResponseRedirect(
                reverse(
                    "form-show", kwargs={"username": username, "id_string": id_string}
                )
            )
        return HttpResponseRedirect(url)
    except (AttributeError, EnketoError) as e:
        error_msg = e
        if isinstance(e, AttributeError):
            error_msg = _("Enketo is not configured for this server!")
        data = {}
        owner = User.objects.get(username__iexact=username)
        data["profile"], __ = UserProfile.objects.get_or_create(user=owner)
        data["xform"] = xform
        data["content_user"] = owner
        data["form_view"] = True
        data["message"] = {
            "type": "alert-error",
            "text": f"Enketo error, reason: {error_msg}",
        }
        data["num_forms"] = owner.xforms.filter(shared__exact=1).count()
        messages.add_message(
            request,
            messages.WARNING,
            _(f"Enketo error: enketo replied {error_msg}"),
            fail_silently=True,
        )
        return render(request, "profile.html", data)

    return HttpResponseRedirect(
        reverse("form-show", kwargs={"username": username, "id_string": id_string})
    )


def edit_data(request, username, id_string, data_id):
    """
    Redirects to Enketo webform to edit a submission with the data_id.
    """
    context = RequestContext(request)
    owner = User.objects.get(username__iexact=username)
    xform_kwargs = {"id_string__iexact": id_string, "user__username__iexact": username}

    xform = get_form(xform_kwargs)
    instance = get_object_or_404(Instance, pk=data_id, xform=xform)
    if not has_edit_permission(xform, owner, request, xform.shared):
        return HttpResponseForbidden(_("Not shared."))
    if not hasattr(settings, "ENKETO_URL"):
        return HttpResponseRedirect(
            reverse("form-show", kwargs={"username": username, "id_string": id_string})
        )

    url = f"{settings.ENKETO_URL}data/edit_url"
    # see commit 220f2dad0e for tmp file creation
    injected_xml = inject_instanceid(instance.xml, instance.uuid)
    return_url = request.build_absolute_uri(
        reverse(
            "submission-instance", kwargs={"username": username, "id_string": id_string}
        )
        + "#/"
        + str(instance.id)
    )
    form_url = get_form_url(request, username, settings.ENKETO_PROTOCOL)

    try:
        url = get_enketo_urls(
            form_url,
            xform.id_string,
            instance_xml=injected_xml,
            instance_id=instance.uuid,
            return_url=return_url,
        )
    except EnketoError as e:
        context.message = {
            "type": "alert-error",
            "text": f"Enketo error, reason: {e}",
        }
        messages.add_message(
            request,
            messages.WARNING,
            _(f"Enketo error: enketo replied {e}"),
            fail_silently=True,
        )
    else:
        if url:
            url = url["edit_url"]
            context.enketo = url
            return HttpResponseRedirect(url)
    return HttpResponseRedirect(
        reverse("form-show", kwargs={"username": username, "id_string": id_string})
    )


def view_submission_list(request, username):
    """
    Submission list view.

    Briefcase Aggregate API view/submissionList.
    """
    form_user = get_object_or_404(User, username__iexact=username)
    __, ___ = UserProfile.objects.get_or_create(user=form_user)
    authenticator = HttpDigestAuthenticator()
    if not authenticator.authenticate(request):
        return authenticator.build_challenge_response()
    id_string = request.GET.get("formId", None)
    xform_kwargs = {"id_string__iexact": id_string, "user__username__iexact": username}

    xform = get_form(xform_kwargs)
    if not has_permission(xform, form_user, request, xform.shared_data):
        return HttpResponseForbidden("Not shared.")
    num_entries = request.GET.get("numEntries", None)
    cursor = request.GET.get("cursor", None)
    instances = xform.instances.filter(deleted_at=None).order_by("pk")

    cursor = _parse_int(cursor)
    if cursor:
        instances = instances.filter(pk__gt=cursor)

    num_entries = _parse_int(num_entries)
    if num_entries:
        instances = instances[:num_entries]

    data = {"instances": instances}

    resumption_cursor = 0
    if instances.count():
        last_instance = instances[instances.count() - 1]
        resumption_cursor = last_instance.pk
    elif instances.count() == 0 and cursor:
        resumption_cursor = cursor

    data["resumptionCursor"] = resumption_cursor

    return render(
        request, "submissionList.xml", data, content_type="text/xml; charset=utf-8"
    )


def view_download_submission(request, username):
    """
    Submission download view.

    Briefcase Aggregate API view/downloadSubmissionList.
    """
    form_user = get_object_or_404(User, username__iexact=username)
    __, ___ = UserProfile.objects.get_or_create(user=form_user)
    authenticator = HttpDigestAuthenticator()
    if not authenticator.authenticate(request):
        return authenticator.build_challenge_response()
    data = {}
    form_id = request.GET.get("formId", None)
    if not isinstance(form_id, six.string_types):
        return HttpResponseBadRequest()
    last_index = form_id.find("[")
    id_string = form_id[0:last_index]
    form_id_parts = form_id.split("/")
    if len(form_id_parts) < 2:
        return HttpResponseBadRequest()

    uuid = _extract_uuid(form_id_parts[1])
    instance = get_object_or_404(
        Instance,
        xform__id_string__iexact=id_string,
        uuid=uuid,
        xform__user__username=username,
        deleted_at__isnull=True,
    )
    xform = instance.xform
    if not has_permission(xform, form_user, request, xform.shared_data):
        return HttpResponseForbidden("Not shared.")
    submission_xml_root_node = instance.get_root_node()
    submission_xml_root_node.setAttribute("instanceID", f"uuid:{instance.uuid}")
    submission_xml_root_node.setAttribute(
        "submissionDate", instance.date_created.isoformat()
    )
    data["submission_data"] = submission_xml_root_node.toxml()
    data["media_files"] = Attachment.objects.filter(instance=instance)
    data["host"] = request.build_absolute_uri().replace(request.get_full_path(), "")

    return render(
        request, "downloadSubmission.xml", data, content_type="text/xml; charset=utf-8"
    )


@require_http_methods(["HEAD", "POST"])
@csrf_exempt
def form_upload(request, username):
    """
    XForm upload view.

    Briefcase Aggregate API /formUpload.
    """
    form_user = get_object_or_404(User, username__iexact=username)
    __, ___ = UserProfile.objects.get_or_create(user=form_user)
    authenticator = HttpDigestAuthenticator()
    if not authenticator.authenticate(request):
        return authenticator.build_challenge_response()
    if form_user != request.user:
        return HttpResponseForbidden(
            _(f"Not allowed to upload form[s] to {form_user} account.")
        )
    if request.method == "HEAD":
        response = OpenRosaResponse(status=204)
        response["Location"] = request.build_absolute_uri().replace(
            request.get_full_path(), f"/{form_user.username}/formUpload"
        )
        return response
    xform_def = request.FILES.get("form_def_file", None)
    content = ""
    status = 400
    if isinstance(xform_def, File):
        do_form_upload = PublishXForm(xform_def, form_user)
        xform = publish_form(do_form_upload.publish_xform)
        status = 201
        if isinstance(xform, XForm):
            content = _(f"{xform.id_string} successfully published.")
        else:
            content = xform["text"]
            if isinstance(content, Exception):
                content = str(content)
                status = 500
            else:
                status = 400
    return OpenRosaResponse(content, status=status)
