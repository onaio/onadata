# -*- coding: utf-8 -*-
"""
logger_tools - Logger app utility functions.
"""
import json
import os
import re
import sys
import tempfile
from builtins import str as text
from datetime import datetime
from hashlib import sha256
from http.client import BadStatusLine
from typing import NoReturn
from wsgiref.util import FileWrapper
from xml.dom import Node
from xml.parsers.expat import ExpatError

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import (
    MultipleObjectsReturned,
    PermissionDenied,
    ValidationError,
)
from django.core.files.storage import get_storage_class
from django.db import DataError, IntegrityError, transaction
from django.db.models import Q
from django.http import (
    HttpResponse,
    HttpResponseNotFound,
    StreamingHttpResponse,
    UnreadablePostError,
)
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import DjangoUnicodeDecodeError
from django.utils.translation import gettext as _

from defusedxml.ElementTree import ParseError, fromstring
from dict2xml import dict2xml
from modilabs.utils.subprocess_timeout import ProcessTimedOut
from multidb.pinning import use_master
from pyxform.errors import PyXFormError
from pyxform.validators.odk_validate import ODKValidateError
from pyxform.xform2json import create_survey_element_from_xml
from rest_framework.response import Response

from onadata.apps.logger.models import Attachment, Instance, XForm, XFormVersion
from onadata.apps.logger.models.instance import (
    FormInactiveError,
    FormIsMergedDatasetError,
    InstanceHistory,
    get_id_string_from_xml_str,
)
from onadata.apps.logger.models.xform import DuplicateUUIDError, XLSFormError
from onadata.apps.logger.xform_instance_parser import (
    AttachmentNameError,
    DuplicateInstance,
    InstanceEmptyError,
    InstanceEncryptionError,
    InstanceFormatError,
    InstanceInvalidUserError,
    InstanceMultipleNodeError,
    NonUniqueFormIdError,
    clean_and_parse_xml,
    get_deprecated_uuid_from_xml,
    get_submission_date_from_xml,
    get_uuid_from_xml,
)
from onadata.apps.messaging.constants import (
    SUBMISSION_CREATED,
    SUBMISSION_EDITED,
    XFORM,
)
from onadata.apps.messaging.serializers import send_message
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.viewer.models.parsed_instance import ParsedInstance
from onadata.apps.viewer.signals import process_submission
from onadata.libs.utils.analytics import TrackObjectEvent
from onadata.libs.utils.common_tags import METADATA_FIELDS
from onadata.libs.utils.common_tools import get_uuid, report_exception
from onadata.libs.utils.model_tools import set_uuid
from onadata.libs.utils.user_auth import get_user_default_project

OPEN_ROSA_VERSION_HEADER = "X-OpenRosa-Version"
HTTP_OPEN_ROSA_VERSION_HEADER = "HTTP_X_OPENROSA_VERSION"
OPEN_ROSA_VERSION = "1.0"
DEFAULT_CONTENT_TYPE = "text/xml; charset=utf-8"
DEFAULT_CONTENT_LENGTH = settings.DEFAULT_CONTENT_LENGTH
REQUIRED_ENCRYPTED_FILE_ELEMENTS = [
    "{http://www.opendatakit.org/xforms/encrypted}base64EncryptedKey",
    "{http://www.opendatakit.org/xforms/encrypted}encryptedXmlFile",
    "{http://opendatakit.org/submissions}base64EncryptedKey",
    "{http://opendatakit.org/submissions}encryptedXmlFile",
]

uuid_regex = re.compile(
    r"<formhub>\s*<uuid>\s*([^<]+)\s*</uuid>\s*</formhub>", re.DOTALL
)


# pylint: disable=invalid-name
User = get_user_model()


def create_xform_version(xform: XForm, user: User) -> XFormVersion:
    """
    Creates an XFormVersion object for the passed in XForm
    """
    versioned_xform = None
    try:
        with transaction.atomic():
            versioned_xform = XFormVersion.objects.create(
                xform=xform,
                xls=xform.xls,
                json=(
                    xform.json
                    if isinstance(xform.json, str)
                    else json.dumps(xform.json)
                ),
                version=xform.version,
                created_by=user,
                xml=xform.xml,
            )
    except IntegrityError:
        pass
    return versioned_xform


# pylint: disable=too-many-arguments
def _get_instance(xml, new_uuid, submitted_by, status, xform, checksum, request=None):
    history = None
    instance = None
    message_verb = SUBMISSION_EDITED
    # check if its an edit submission
    old_uuid = get_deprecated_uuid_from_xml(xml)
    if old_uuid:
        instance = Instance.objects.filter(uuid=old_uuid, xform_id=xform.pk).first()
        history = (
            InstanceHistory.objects.filter(
                xform_instance__xform_id=xform.pk, uuid=new_uuid
            )
            .only("xform_instance")
            .first()
        )

        if instance:
            # edits
            check_edit_submission_permissions(submitted_by, xform)

            last_edited = timezone.now()
            InstanceHistory.objects.create(
                checksum=instance.checksum,
                xml=instance.xml,
                xform_instance=instance,
                uuid=old_uuid,
                user=submitted_by,
                geom=instance.geom,
                submission_date=instance.last_edited or instance.date_created,
            )
            instance.xml = xml
            instance.last_edited = last_edited
            instance.uuid = new_uuid
            instance.checksum = checksum
            instance.save()

            # call webhooks
            process_submission.send(sender=instance.__class__, instance=instance)
        elif history:
            instance = history.xform_instance
    if old_uuid is None or (instance is None and history is None):
        # new submission
        message_verb = SUBMISSION_CREATED
        instance = Instance.objects.create(
            xml=xml, user=submitted_by, status=status, xform=xform, checksum=checksum
        )

    # send notification on submission creation
    send_message(
        instance_id=instance.id,
        target_id=instance.xform.id,
        target_type=XFORM,
        user=instance.user or instance.xform.user,
        message_verb=message_verb,
    )
    return instance


def dict2xform(jsform, form_id, root=None, username=None, gen_uuid=False):
    """
    Converts a dictionary containing submission data into an XML
    Submission for the appropriate form.

    :param jsform (dict): A python dictionary object containing the submission
                          data
    :param form_id (str or XForm): An XForm object or a string value
                                   representing the forms id_string
    :param root (str): An optional string that should be used as the
                       root nodes name. Defaults to None
    :param: username (str): An optional string representing a users
                            username. Used alongside the `form_id` to
                            locate the XForm object the user is
                            trying to submit data too. Defaults to None
    :returns: Returns a string containing the Submission XML
    :rtype: str
    """
    if not root:
        if username:
            if isinstance(form_id, XForm):
                root = form_id.survey.name
            else:
                form = XForm.objects.filter(
                    id_string__iexact=form_id,
                    user__username__iexact=username,
                    deleted_at__isnull=True,
                ).first()
                root = form.survey.name if form else "data"
        else:
            root = "data"

    if gen_uuid:
        jsform["meta"] = {"instanceID": "uuid:" + get_uuid(hex_only=False)}

    return f"<?xml version='1.0' ?><{root} id='{form_id}'>{dict2xml(jsform)}</{root}>"


def get_first_record(queryset):
    """
    Returns the first item in a queryset sorted by id.
    """
    records = sorted(list(queryset), key=lambda k: k.id)
    if records:
        return records[0]

    return None


def get_uuid_from_submission(xml):
    """Extracts and returns the UUID from a submission XML."""
    # parse UUID from uploaded XML
    split_xml = uuid_regex.split(xml.decode("utf-8"))

    # check that xml has UUID
    return split_xml[1] if len(split_xml) > 1 else None


def get_xform_from_submission(xml, username, uuid=None, request=None):
    """Gets the submissions target XForm.

    Retrieves the target XForm by either utilizing the `uuid` param
    or the `uuid` retrievable from the `xml` or the `id_string`
    retrievable from the XML. Only returns form if `request_user` has
    permission to submit.

    :param (str) xml: The submission in XML form
    :param (str) username: The owner of the target XForm
    :param (str) uuid: The target XForms universally unique identifier.
    Default: None
    :param (django.http.request) request: Request object. Default: None
    """
    uuid = uuid or get_uuid_from_submission(xml)

    if not username and not uuid:
        raise InstanceInvalidUserError()

    if uuid:
        # try find the form by its uuid which is the ideal condition
        if XForm.objects.filter(uuid=uuid, deleted_at__isnull=True).count() > 0:
            xform = XForm.objects.get(uuid=uuid, deleted_at__isnull=True)
            # If request is present, verify that the request user
            # has the correct permissions
            if request:
                try:
                    # Verify request user has permission
                    # to make submissions to the XForm
                    check_submission_permissions(request, xform)
                    return xform
                except PermissionDenied as e:
                    # Check if the owner_username is equal to the XForm owner
                    # Assumption: If the owner_username is equal to the XForm
                    # owner we've retrieved the correct form.
                    if username and xform.user.username == username:
                        raise e from e
            else:
                return xform

    id_string = get_id_string_from_xml_str(xml)
    try:
        return get_object_or_404(
            XForm,
            id_string__iexact=id_string,
            user__username__iexact=username,
            deleted_at__isnull=True,
        )
    except MultipleObjectsReturned as e:
        raise NonUniqueFormIdError() from e


def _has_edit_xform_permission(xform, user):
    if isinstance(xform, XForm) and isinstance(user, User):
        return user.has_perm("logger.change_xform", xform)

    return False


def check_edit_submission_permissions(request_user, xform):
    """Checks edit submission permissions."""
    if xform and request_user and request_user.is_authenticated:
        requires_auth = xform.user.profile.require_auth
        has_edit_perms = _has_edit_xform_permission(xform, request_user)

        if requires_auth and not has_edit_perms:
            raise PermissionDenied(
                _(
                    "%(request_user)s is not allowed to make edit submissions "
                    "to %(form_user)s's %(form_title)s form."
                    % {
                        "request_user": request_user,
                        "form_user": xform.user,
                        "form_title": xform.title,
                    }
                )
            )


def check_submission_permissions(request, xform):
    """Check that permission is required and the request user has permission.

    The user does no have permissions iff:
        * the user is authed,
        * either the profile or the form require auth,
        * the xform user is not submitting.

    Since we have a username, the Instance creation logic will
    handle checking for the forms existence by its id_string.

    :returns: None.
    :raises: PermissionDenied based on the above criteria.
    """
    requires_authentication = request and (
        xform.user.profile.require_auth
        or xform.require_auth
        or request.path == "/submission"
    )
    if (
        requires_authentication
        and xform.user != request.user
        and not request.user.has_perm("report_xform", xform)
    ):
        raise PermissionDenied(
            _(
                "%(request_user)s is not allowed to make submissions "
                "to %(form_user)s's %(form_title)s form."
                % {
                    "request_user": request.user,
                    "form_user": xform.user,
                    "form_title": xform.title,
                }
            )
        )


def check_submission_encryption(xform: XForm, xml: bytes) -> NoReturn:
    """
    Check that the submission is encrypted or unencrypted depending on the
    encryption status of an XForm.

    The submission is invalid if the XForm's encryption status is different
    from the submissions
    """
    submission_encrypted = False
    submission_element = fromstring(xml)
    encrypted_attrib = submission_element.attrib.get("encrypted")
    required_encryption_elems = [
        elem.tag
        for elem in submission_element
        if elem.tag in REQUIRED_ENCRYPTED_FILE_ELEMENTS
    ]
    encryption_elems_num = len(required_encryption_elems)

    # Check the validity of the submission
    if encrypted_attrib == "yes" or encryption_elems_num > 1:
        if (
            not encryption_elems_num == 2 or not encrypted_attrib == "yes"
        ) and xform.encrypted:
            raise InstanceFormatError(_("Encrypted submission incorrectly formatted."))
        submission_encrypted = True

    if xform.encrypted and not submission_encrypted:
        raise InstanceEncryptionError(
            _("Unencrypted submissions are not allowed for encrypted forms.")
        )


def update_attachment_tracking(instance):
    """
    Takes an Instance object and updates attachment tracking fields
    """
    instance.total_media = instance.num_of_media
    instance.media_count = instance.attachments_count
    instance.media_all_received = instance.media_count == instance.total_media
    instance.save(
        update_fields=["total_media", "media_count", "media_all_received", "json"]
    )


def save_attachments(xform, instance, media_files, remove_deleted_media=False):
    """
    Saves attachments for the given instance/submission.
    """
    # upload_path = os.path.join(instance.xform.user.username, 'attachments')

    for f in media_files:
        filename, extension = os.path.splitext(f.name)
        extension = extension.replace(".", "")
        content_type = "text/xml" if extension == Attachment.OSM else f.content_type
        if extension == Attachment.OSM and not xform.instances_with_osm:
            xform.instances_with_osm = True
            xform.save()
        filename = os.path.basename(f.name)
        # Validate Attachment file name length
        if len(filename) > 100:
            raise AttachmentNameError(filename)
        media_in_submission = filename in instance.get_expected_media() or [
            (
                instance.xml.decode("utf-8").find(filename) != -1
                if isinstance(instance.xml, bytes)
                else instance.xml.find(filename) != -1
            )
        ]
        if media_in_submission:
            Attachment.objects.get_or_create(
                xform=xform,
                instance=instance,
                media_file=f,
                mimetype=content_type,
                name=filename,
                extension=extension,
                user=instance.user,
            )
    if remove_deleted_media:
        instance.soft_delete_attachments()

    update_attachment_tracking(instance)


def save_submission(
    xform,
    xml,
    media_files,
    new_uuid,
    submitted_by,
    status,
    date_created_override,
    checksum,
    request=None,
):
    """Persist a submission into the ParsedInstance model."""
    if not date_created_override:
        date_created_override = get_submission_date_from_xml(xml)

    instance = _get_instance(
        xml, new_uuid, submitted_by, status, xform, checksum, request
    )
    save_attachments(xform, instance, media_files, remove_deleted_media=True)

    # override date created if required
    if date_created_override:
        if not timezone.is_aware(date_created_override):
            # default to utc?
            date_created_override = timezone.make_aware(
                date_created_override, timezone.utc
            )
        instance.date_created = date_created_override
        instance.save()

    if instance.xform is not None:
        instance.save()
        pi, created = ParsedInstance.objects.get_or_create(instance=instance)
        if not created:
            pi.save()  # noqa

    return instance


def get_filtered_instances(*args, **kwargs):
    """Get filtered instances - mainly to allow mocking in tests"""

    return Instance.objects.filter(*args, **kwargs)


# pylint: disable=too-many-locals
def create_instance(
    username,
    xml_file,
    media_files,
    status="submitted_via_web",
    uuid=None,
    date_created_override=None,
    request=None,
):
    """
    I used to check if this file had been submitted already, I've
    taken this out because it was too slow. Now we're going to create
    a way for an admin to mark duplicate instances. This should
    simplify things a bit.
    Submission cases:
    * If there is a username and no uuid, submitting an old ODK form.
    * If there is a username and a uuid, submitting a new ODK form.
    """
    instance = None
    submitted_by = request.user if request and request.user.is_authenticated else None

    if username:
        username = username.lower()

    xml = xml_file.read()
    xform = get_xform_from_submission(xml, username, uuid, request=request)
    check_submission_permissions(request, xform)
    check_submission_encryption(xform, xml)
    checksum = sha256(xml).hexdigest()

    new_uuid = get_uuid_from_xml(xml)
    filtered_instances = get_filtered_instances(
        Q(checksum=checksum) | Q(uuid=new_uuid), xform_id=xform.pk
    )
    existing_instance = get_first_record(filtered_instances.only("id"))
    if existing_instance and (new_uuid or existing_instance.xform.has_start_time):
        # ensure we have saved the extra attachments
        with transaction.atomic():
            save_attachments(
                xform, existing_instance, media_files, remove_deleted_media=True
            )
            existing_instance.save(update_fields=["json", "date_modified"])

        # Ignore submission as a duplicate IFF
        #  * a submission's XForm collects start time
        #  * the submitted XML is an exact match with one that
        #    has already been submitted for that user.
        return DuplicateInstance()

    # get new and deprecated UUIDs
    history = (
        InstanceHistory.objects.filter(
            xform_instance__xform_id=xform.pk,
            xform_instance__deleted_at__isnull=True,
            uuid=new_uuid,
        )
        .only("xform_instance")
        .first()
    )

    if history:
        duplicate_instance = history.xform_instance
        # ensure we have saved the extra attachments
        with transaction.atomic():
            save_attachments(
                xform, duplicate_instance, media_files, remove_deleted_media=True
            )
            duplicate_instance.save()

        return DuplicateInstance()

    try:
        with transaction.atomic():
            if isinstance(xml, bytes):
                xml = xml.decode("utf-8")
            instance = save_submission(
                xform,
                xml,
                media_files,
                new_uuid,
                submitted_by,
                status,
                date_created_override,
                checksum,
                request,
            )
    except IntegrityError:
        instance = get_first_record(
            Instance.objects.filter(
                Q(checksum=checksum) | Q(uuid=new_uuid), xform_id=xform.pk
            )
        )

        if instance:
            attachment_names = [
                a.media_file.name.split("/")[-1]
                for a in Attachment.objects.filter(instance=instance)
            ]
            media_files = [f for f in media_files if f.name not in attachment_names]
            save_attachments(xform, instance, media_files)
            instance.save()

        instance = DuplicateInstance()
    return instance


# pylint: disable=too-many-branches,too-many-statements
@use_master
def safe_create_instance(  # noqa C901
    username,
    xml_file,
    media_files,
    uuid,
    request,
    instance_status: str = "submitted_via_web",
):
    """Create an instance and catch exceptions.

    :returns: A list [error, instance] where error is None if there was no
        error.
    """
    error = instance = None

    try:
        instance = create_instance(
            username,
            xml_file,
            media_files,
            uuid=uuid,
            request=request,
            status=instance_status,
        )
    except InstanceInvalidUserError:
        error = OpenRosaResponseBadRequest(_("Username or ID required."))
    except InstanceEmptyError:
        error = OpenRosaResponseBadRequest(
            _("Received empty submission. No instance was created")
        )
    except InstanceEncryptionError as e:
        error = OpenRosaResponseBadRequest(text(e))
    except InstanceFormatError as e:
        error = OpenRosaResponseBadRequest(text(e))
    except (FormInactiveError, FormIsMergedDatasetError) as e:
        error = OpenRosaResponseNotAllowed(text(e))
    except XForm.DoesNotExist:
        error = OpenRosaResponseNotFound(_("Form does not exist on this account"))
    except (ExpatError, ParseError):
        error = OpenRosaResponseBadRequest(_("Improperly formatted XML."))
    except AttachmentNameError:
        response = OpenRosaResponseBadRequest(
            _("Attachment file name exceeds 100 chars")
        )
        response.status_code = 400
        error = response
    except DuplicateInstance:
        response = OpenRosaResponse(_("Duplicate submission"))
        response.status_code = 202
        if request:
            response["Location"] = request.build_absolute_uri(request.path)
        error = response
    except PermissionDenied as e:
        error = OpenRosaResponseForbidden(e)
    except UnreadablePostError as e:
        error = OpenRosaResponseBadRequest(_(f"Unable to read submitted file: {e}"))
    except InstanceMultipleNodeError as e:
        error = OpenRosaResponseBadRequest(e)
    except DjangoUnicodeDecodeError:
        error = OpenRosaResponseBadRequest(
            _("File likely corrupted during transmission, please try later.")
        )
    except NonUniqueFormIdError:
        error = OpenRosaResponseBadRequest(
            _("Unable to submit because there are multiple forms with this formID.")
        )
    except DataError as e:
        error = OpenRosaResponseBadRequest((str(e)))
    if isinstance(instance, DuplicateInstance):
        response = OpenRosaResponse(_("Duplicate submission"))
        response.status_code = 202
        if request:
            response["Location"] = request.build_absolute_uri(request.path)
        error = response
        instance = None
    return [error, instance]


def response_with_mimetype_and_name(
    mimetype,
    name,
    extension=None,
    show_date=True,
    file_path=None,
    use_local_filesystem=False,
    full_mime=False,
):
    """Returns a HttpResponse with Content-Disposition header set

    Triggers a download on the browser."""
    if extension is None:
        extension = mimetype
    if not full_mime:
        mimetype = f"application/{mimetype}"
    if file_path:
        try:
            if not use_local_filesystem:
                default_storage = get_storage_class()()
                wrapper = FileWrapper(default_storage.open(file_path))
                response = StreamingHttpResponse(wrapper, content_type=mimetype)
                response["Content-Length"] = default_storage.size(file_path)
            else:
                # pylint: disable=consider-using-with
                wrapper = FileWrapper(open(file_path, "rb"))
                response = StreamingHttpResponse(wrapper, content_type=mimetype)
                response["Content-Length"] = os.path.getsize(file_path)
        except IOError:
            response = HttpResponseNotFound(_("The requested file could not be found."))
    else:
        response = HttpResponse(content_type=mimetype)
    response["Content-Disposition"] = generate_content_disposition_header(
        name, extension, show_date
    )
    return response


def generate_content_disposition_header(name, extension, show_date=True):
    """Returns the a Content-Description header formatting string,"""
    if name is None:
        return "attachment;"
    if show_date:
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        name = f"{name}-{timestamp}"
    return f"attachment; filename={name}.{extension}"


def store_temp_file(data):
    """Creates a temporary file with the ``data`` and returns it."""
    ret = None
    with tempfile.TemporaryFile() as tmp:
        tmp.write(data)
        tmp.seek(0)
        ret = tmp

    return ret


def publish_form(callback):
    """
    Calls the callback function to publish a XLSForm and returns appropriate
    message depending on exception throw during publishing of a XLSForm.
    """
    try:
        return callback()
    except (PyXFormError, XLSFormError, ODKValidateError) as e:
        return {"type": "alert-error", "text": text(e)}
    except IntegrityError:
        return {
            "type": "alert-error",
            "text": _("Form with this id or SMS-keyword already exists."),
        }
    except ProcessTimedOut:
        # catch timeout errors
        return {
            "type": "alert-error",
            "text": _("Form validation timeout, please try again."),
        }
    except (MemoryError, OSError, BadStatusLine):
        return {
            "type": "alert-error",
            "text": _(
                ("An error occurred while publishing the form. Please try again.")
            ),
        }
    except (AttributeError, DuplicateUUIDError, ValidationError) as e:
        report_exception(f"Form publishing exception: {e}", text(e), sys.exc_info())
        return {"type": "alert-error", "text": text(e)}


@TrackObjectEvent(
    user_field="user",
    properties={"created_by": "user", "xform_id": "pk", "xform_name": "title"},
    additional_context={"from": "Publish XLS Form"},
)
@transaction.atomic()
def publish_xls_form(xls_file, user, project, id_string=None, created_by=None):
    """Create or update DataDictionary with xls_file, user
    id_string is optional when updating
    """
    # get or create DataDictionary based on user and id string
    if id_string:
        dd = DataDictionary.objects.get(user=user, id_string=id_string, project=project)
        dd.xls = xls_file
        dd.save()
    else:
        dd = DataDictionary.objects.create(
            created_by=created_by or user, user=user, xls=xls_file, project=project
        )

    # Create an XFormVersion object for the published XLSForm
    create_xform_version(dd, user)
    return dd


@TrackObjectEvent(
    user_field="user",
    properties={"created_by": "user", "xform_id": "pk", "xform_name": "title"},
    additional_context={"from": "Publish XML Form"},
)
def publish_xml_form(xml_file, user, project, id_string=None, created_by=None):
    """Publish an XML XForm."""
    xml = xml_file.read()
    if isinstance(xml, bytes):
        xml = xml.decode("utf-8")
    survey = create_survey_element_from_xml(xml)
    form_json = survey.to_json()
    if id_string:
        dd = DataDictionary.objects.get(user=user, id_string=id_string, project=project)
        dd.xml = xml
        dd.json = form_json
        dd.mark_start_time_boolean()
        set_uuid(dd)
        dd.set_uuid_in_xml()
        dd.set_hash()
        dd.save()
    else:
        created_by = created_by or user
        dd = DataDictionary(
            created_by=created_by, user=user, xml=xml, json=form_json, project=project
        )
        dd.mark_start_time_boolean()
        set_uuid(dd)
        dd.set_uuid_in_xml(file_name=xml_file.name)
        dd.set_hash()
        dd.save()

    # Create an XFormVersion object for the published XLSForm
    create_xform_version(dd, user)
    return dd


def remove_metadata_fields(data):
    """
    Clean out unneccessary metadata fields
    """
    for field in METADATA_FIELDS:
        if field in data:
            if isinstance(data, list):
                data.remove(field)
            else:
                del data[field]
    return data


def set_default_openrosa_headers(response):
    """Sets the default OpenRosa headers into a ``response`` object."""
    response["Content-Type"] = "text/html; charset=utf-8"
    response["X-OpenRosa-Accept-Content-Length"] = DEFAULT_CONTENT_LENGTH
    dt = timezone.localtime().strftime("%a, %d %b %Y %H:%M:%S %Z")
    response["Date"] = dt
    response[OPEN_ROSA_VERSION_HEADER] = OPEN_ROSA_VERSION
    response["Content-Type"] = DEFAULT_CONTENT_TYPE


class BaseOpenRosaResponse(HttpResponse):
    """The base HTTP response class with OpenRosa headers."""

    status_code = 201

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_default_openrosa_headers(self)


class OpenRosaResponse(BaseOpenRosaResponse):
    """An HTTP response class with OpenRosa headers for the created response."""

    status_code = 201

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = self.content
        # wrap content around xml
        self.content = f"""<?xml version='1.0' encoding='UTF-8' ?>
<OpenRosaResponse xmlns="http://openrosa.org/http/response">
        <message nature="">{self.content}</message>
</OpenRosaResponse>"""


class OpenRosaResponseNotFound(OpenRosaResponse):
    """An HTTP response class with OpenRosa headers for the Not Found response."""

    status_code = 404


class OpenRosaResponseBadRequest(OpenRosaResponse):
    """An HTTP response class with OpenRosa headers for the Bad Request response."""

    status_code = 400


class OpenRosaResponseNotAllowed(OpenRosaResponse):
    """An HTTP response class with OpenRosa headers for the Not Allowed response."""

    status_code = 405


class OpenRosaResponseForbidden(OpenRosaResponse):
    """An HTTP response class with OpenRosa headers for the Forbidden response."""

    status_code = 403


class OpenRosaNotAuthenticated(Response):
    """An HTTP response class with OpenRosa headers for the Not Authenticated
    response."""

    status_code = 401

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_default_openrosa_headers(self)


def inject_instanceid(xml_str, uuid):
    if get_uuid_from_xml(xml_str) is None:
        xml = clean_and_parse_xml(xml_str)
        children = xml.childNodes
        if children.length == 0:
            raise ValueError(_("XML string must have a survey element."))

        # check if we have a meta tag
        survey_node = children.item(0)
        meta_tags = [
            n
            for n in survey_node.childNodes
            if n.nodeType == Node.ELEMENT_NODE and n.tagName.lower() == "meta"
        ]
        if len(meta_tags) == 0:
            meta_tag = xml.createElement("meta")
            xml.documentElement.appendChild(meta_tag)
        else:
            meta_tag = meta_tags[0]

        # check if we have an instanceID tag
        uuid_tags = [
            n
            for n in meta_tag.childNodes
            if n.nodeType == Node.ELEMENT_NODE and n.tagName == "instanceID"
        ]
        if len(uuid_tags) == 0:
            uuid_tag = xml.createElement("instanceID")
            meta_tag.appendChild(uuid_tag)
        else:
            uuid_tag = uuid_tags[0]
        # insert meta and instanceID
        text_node = xml.createTextNode(f"uuid:{uuid}")
        uuid_tag.appendChild(text_node)
        return xml.toxml()
    return xml_str


class PublishXForm:
    "A class to publish an XML XForm file."

    def __init__(self, xml_file, user):
        self.xml_file = xml_file
        self.user = user
        self.project = get_user_default_project(user)

    def publish_xform(self):
        """Publish an XForm XML file."""
        return publish_xml_form(self.xml_file, self.user, self.project)
