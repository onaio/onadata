# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""
logger_tools - Logger app utility functions.
"""

import importlib
import json
import logging
import os
import re
import sys
import tempfile
from builtins import str as text
from collections import OrderedDict
from datetime import datetime, timedelta
from datetime import timezone as tz
from hashlib import sha256
from http.client import BadStatusLine
from typing import Any
from wsgiref.util import FileWrapper
from xml.dom import Node
from xml.parsers.expat import ExpatError

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import (
    MultipleObjectsReturned,
    PermissionDenied,
    ValidationError,
)
from django.core.files.storage import storages
from django.db import DataError, IntegrityError, transaction
from django.db.models import F, Q
from django.db.models.query import QuerySet
from django.http import (
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseRedirect,
    StreamingHttpResponse,
    UnreadablePostError,
)
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import DjangoUnicodeDecodeError
from django.utils.translation import gettext as _

import boto3
from botocore.client import Config
from defusedxml.ElementTree import ParseError, fromstring
from dict2xml import dict2xml
from modilabs.utils.subprocess_timeout import ProcessTimedOut
from multidb.pinning import use_master
from pyxform.errors import PyXFormError
from pyxform.validators.odk_validate import ODKValidateError
from pyxform.xform2json import create_survey_element_from_xml
from rest_framework.response import Response

from onadata.apps.logger.models import (
    Attachment,
    Instance,
    RegistrationForm,
    XForm,
    XFormVersion,
)
from onadata.apps.logger.models.entity import Entity
from onadata.apps.logger.models.entity_list import EntityList
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
    get_entity_uuid_from_xml,
    get_meta_from_xml,
    get_submission_date_from_xml,
    get_uuid_from_xml,
)
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.messaging.constants import (
    SUBMISSION_CREATED,
    SUBMISSION_DELETED,
    SUBMISSION_EDITED,
    XFORM,
)
from onadata.apps.messaging.serializers import send_message
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.viewer.models.parsed_instance import ParsedInstance
from onadata.apps.viewer.signals import process_submission
from onadata.libs.utils.analytics import TrackObjectEvent
from onadata.libs.utils.cache_tools import (
    ELIST_FAILOVER_REPORT_SENT,
    ELIST_NUM_ENTITIES,
    ELIST_NUM_ENTITIES_CREATED_AT,
    ELIST_NUM_ENTITIES_IDS,
    ELIST_NUM_ENTITIES_LOCK,
    XFORM_SUBMISSIONS_DELETING,
    safe_delete,
    set_cache_with_lock,
)
from onadata.libs.utils.common_tags import EXPORT_COLUMNS_REGISTER, METADATA_FIELDS
from onadata.libs.utils.common_tools import get_uuid, report_exception
from onadata.libs.utils.model_tools import queryset_iterator, set_uuid
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

logger = logging.getLogger(__name__)


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


# pylint: disable=too-many-arguments, too-many-positional-arguments
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


def is_valid_encrypted_submission(xform_is_encrypted: bool, xml: bytes) -> bool:
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
        ) and xform_is_encrypted:
            raise InstanceFormatError(_("Encrypted submission incorrectly formatted."))
        submission_encrypted = True

    return submission_encrypted


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
            date_created_override = timezone.make_aware(date_created_override, tz.utc)
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
    submission_encrypted = is_valid_encrypted_submission(xform.encrypted, xml)
    if xform.encrypted and not submission_encrypted:
        raise InstanceEncryptionError(
            _("Unencrypted submissions are not allowed for encrypted forms.")
        )

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


def generate_aws_media_url(
    file_path: str, content_disposition: str, expiration: int = 3600
):
    """Generate S3 URL."""
    s3_class = storages.create_storage(
        {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"}
    )
    bucket_name = s3_class.bucket.name
    aws_endpoint_url = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
    s3_config = Config(
        signature_version=getattr(settings, "AWS_S3_SIGNATURE_VERSION", "s3v4"),
        region_name=getattr(settings, "AWS_S3_REGION_NAME", None),
    )
    s3_client = boto3.client(
        "s3",
        config=s3_config,
        endpoint_url=aws_endpoint_url,
        aws_access_key_id=s3_class.access_key,
        aws_secret_access_key=s3_class.secret_key,
    )

    # Generate a presigned URL for the S3 object
    return s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket_name,
            "Key": file_path,
            "ResponseContentDisposition": content_disposition,
            "ResponseContentType": "application/octet-stream",
        },
        ExpiresIn=expiration,
    )


def generate_media_url_with_sas(file_path: str, expiration: int = 3600):
    """
    Generate Azure storage URL.
    """
    # pylint: disable=import-outside-toplevel
    from azure.storage.blob import AccountSasPermissions, generate_blob_sas

    account_name = getattr(settings, "AZURE_ACCOUNT_NAME", "")
    container_name = getattr(settings, "AZURE_CONTAINER", "")
    media_url = (
        f"https://{account_name}.blob.core.windows.net/{container_name}/{file_path}"
    )
    sas_token = generate_blob_sas(
        account_name=account_name,
        account_key=getattr(settings, "AZURE_ACCOUNT_KEY", ""),
        container_name=container_name,
        blob_name=file_path,
        permission=AccountSasPermissions(read=True),
        expiry=timezone.now() + timedelta(seconds=expiration),
    )
    return f"{media_url}?{sas_token}"


def get_storages_media_download_url(
    file_path: str, content_disposition: str, expires_in=3600
) -> str | None:
    """Get the media download URL for the storages backend.

    :param file_path: The path to the media file.
    :param content_disposition: The content disposition header.
    :param expires_in: The expiration time in seconds.
    :returns: The media download URL.
    """
    s3_class = None
    azure_class = None
    default_storage = storages["default"]
    url = None

    try:
        s3_class = storages.create_storage(
            {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"}
        )
    except ModuleNotFoundError:
        pass

    try:
        azure_class = storages.create_storage(
            {"BACKEND": "storages.backends.azure_storage.AzureStorage"}
        )
    except ModuleNotFoundError:
        pass

    # Check if the storage backend is S3
    if isinstance(default_storage, type(s3_class)):
        try:
            url = generate_aws_media_url(file_path, content_disposition, expires_in)
        except Exception as error:  # pylint: disable=broad-exception-caught
            logging.exception(error)

    # Check if the storage backend is Azure
    elif isinstance(default_storage, type(azure_class)):
        try:
            url = generate_media_url_with_sas(file_path, expires_in)
        except Exception as error:  # pylint: disable=broad-exception-caught
            logging.error(error)

    return url


def response_with_mimetype_and_name(
    mimetype,
    name,
    extension=None,
    show_date=True,
    file_path=None,
    use_local_filesystem=False,
    full_mime=False,
    expires_in=3600,
):
    """Returns a HttpResponse with Content-Disposition header set

    Triggers a download on the browser."""
    if extension is None:
        extension = mimetype

    if not full_mime:
        mimetype = f"application/{mimetype}"

    content_disposition = generate_content_disposition_header(
        name, extension, show_date
    )
    not_found_response = HttpResponseNotFound(
        _("The requested file could not be found.")
    )

    if file_path:
        if not use_local_filesystem:
            download_url = get_storages_media_download_url(
                file_path, content_disposition, expires_in
            )
            if download_url is not None:
                return HttpResponseRedirect(download_url)

            try:
                default_storage = storages["default"]
                wrapper = FileWrapper(default_storage.open(file_path))
                response = StreamingHttpResponse(wrapper, content_type=mimetype)
                response["Content-Length"] = default_storage.size(file_path)

            except IOError as error:
                logging.exception(error)
                response = not_found_response

        else:
            try:
                # pylint: disable=consider-using-with
                wrapper = FileWrapper(open(file_path, "rb"))
                response = StreamingHttpResponse(wrapper, content_type=mimetype)
                response["Content-Length"] = os.path.getsize(file_path)
            except IOError as error:
                logging.exception(error)
                response = not_found_response
    else:
        response = HttpResponse(content_type=mimetype)
    response["Content-Disposition"] = content_disposition
    return response


def generate_content_disposition_header(name, extension, show_date=True):
    """Returns the a Content-Description header formatting string,"""
    if name is None:
        return "attachment;"
    if show_date:
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        name = f"{name}-{timestamp}"
    # The filename is enclosed in quotes because it ensures that special characters,
    # spaces, or punctuation in the filename are correctly interpreted by browsers
    # and clients. This is particularly important for filenames that may contain
    # spaces or non-ASCII characters.
    return f'attachment; filename="{name}.{extension}"'


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
    """Adds the `uuid` as the <instanceID/> to an XML string `xml_str`."""
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


class PublishXForm:  # pylint: disable=too-few-public-methods
    "A class to publish an XML XForm file."

    def __init__(self, xml_file, user):
        self.xml_file = xml_file
        self.user = user
        self.project = get_user_default_project(user)

    def publish_xform(self):
        """Publish an XForm XML file."""
        return publish_xml_form(self.xml_file, self.user, self.project)


def get_entity_json_from_instance(
    instance: Instance, registration_form: RegistrationForm
) -> dict:
    """Parses Instance json and returns Entity json

    Args:
        instance (Instance): Submission to create Entity

    Returns:
        dict: Entity properties
    """
    instance_json: dict[str, Any] = instance.get_dict()
    # Getting a mapping of save_to field to the field name
    mapped_properties = registration_form.get_save_to(instance.version)
    # Field names with an alias defined
    property_fields = list(mapped_properties.values())

    def get_field_alias(field_name: str) -> str:
        """Get the alias (save_to value) of a form field"""
        for alias, field in mapped_properties.items():
            if field == field_name:
                return alias

        return field_name

    def parse_instance_json(data: dict[str, Any]) -> None:
        """Parse the original json, replacing field names with their alias

        The data keys are modified in place
        """
        for field_name in list(data):
            field_data = data[field_name]
            del data[field_name]

            if field_name.startswith("formhub"):
                continue

            if field_name.startswith("meta"):
                if field_name == "meta/entity/label":
                    data["label"] = field_data

                continue

            # We extract field names within grouped sections
            ungrouped_field_name = field_name.split("/")[-1]

            if ungrouped_field_name in property_fields:
                field_alias = get_field_alias(ungrouped_field_name)
                data[field_alias] = field_data

    parse_instance_json(instance_json)

    return instance_json


def create_entity_from_instance(
    instance: Instance, registration_form: RegistrationForm
) -> Entity:
    """Create an Entity

    Args:
        instance (Instance): Submission from which the Entity is created from
        registration_form (RegistrationForm): RegistrationForm creating the
        Entity

    Returns:
        Entity: A newly created Entity
    """
    entity_json = get_entity_json_from_instance(instance, registration_form)
    entity_list = registration_form.entity_list
    entity = Entity.objects.create(
        entity_list=entity_list,
        json=entity_json,
        uuid=get_entity_uuid_from_xml(instance.xml),
    )
    entity.history.create(
        registration_form=registration_form,
        xml=instance.xml,
        instance=instance,
        form_version=instance.version,
        json=entity_json,
        created_by=instance.user,
    )

    return entity


def update_entity_from_instance(
    uuid: str, instance: Instance, registration_form: RegistrationForm
) -> Entity | None:
    """Updates Entity

    Args:
        uuid (str): uuid of the Entity to be updated
        instance (Instance): Submission that updates an Entity

    Returns:
        Entity | None: updated Entity if uuid valid, else None
    """
    try:
        entity = Entity.objects.get(uuid=uuid)

    except Entity.DoesNotExist as err:
        logger.exception(err)
        return None

    patch_data = get_entity_json_from_instance(instance, registration_form)
    entity.json = {**entity.json, **patch_data}
    entity.save()
    entity.history.create(
        registration_form=registration_form,
        xml=instance.xml,
        instance=instance,
        form_version=instance.version,
        json=entity.json,
        created_by=instance.user,
    )

    return entity


def soft_delete_entities_bulk(entity_qs: QuerySet[Entity], deleted_by=None) -> None:
    """Soft delete Entities in bulk

    Args:
        entity_qs QuerySet(Entity): Entity queryset
        deleted_by (User): User initiating the delete
    """
    for entity in queryset_iterator(entity_qs):
        entity.soft_delete(deleted_by)


def create_or_update_entity_from_instance(instance: Instance) -> None:
    """Create or Update Entity from Instance

    Args:
        instance (Instance): Instance to create/update Entity from
    """
    registration_form_qs = RegistrationForm.objects.filter(
        xform=instance.xform, is_active=True
    )
    entity_node = get_meta_from_xml(instance.xml, "entity")

    if not registration_form_qs.exists() or not entity_node:
        return

    registration_form = registration_form_qs.first()
    mutation_success_checks = ["1", "true"]
    entity_uuid = entity_node.getAttribute("id")
    exists = False

    if entity_uuid is not None:
        exists = Entity.objects.filter(uuid=entity_uuid).exists()

    if exists and entity_node.getAttribute("update") in mutation_success_checks:
        # Update Entity
        update_entity_from_instance(entity_uuid, instance, registration_form)

    elif not exists and entity_node.getAttribute("create") in mutation_success_checks:
        # Create Entity
        create_entity_from_instance(instance, registration_form)


def _inc_elist_num_entities_db(pk: int, count=1) -> None:
    """Increment EntityList `num_entities` counter in the database

    Args:
        pk (int): Primary key for EntityList
        count (int): Value to increase by
    """
    # Using Queryset.update ensures we do not call the model's save method and
    # signals
    EntityList.objects.filter(pk=pk).update(num_entities=F("num_entities") + count)


def _dec_elist_num_entities_db(pk: int, count=1) -> None:
    """Decrement EntityList `num_entities` counter in the database

    Args:
        pk (int): Primary key for EntityList
        count (int): Value to decrease by
    """
    # Using Queryset.update ensures we do not call the model's save method and
    # signals
    EntityList.objects.filter(pk=pk).update(num_entities=F("num_entities") - count)


def _inc_elist_num_entities_cache(pk: int) -> None:
    """Increment EntityList `num_entities` counter in cache

    Args:
        pk (int): Primary key for EntityList
    """
    counter_cache_key = f"{ELIST_NUM_ENTITIES}{pk}"
    # Cache timeout is None (no expiry). A background task should be run
    # periodically to persist the cached counters to the db
    # and delete the cache. If we were to set a timeout, the cache could
    # expire before the next periodic run and data will be lost.
    counter_cache_ttl = None
    counter_cache_created = cache.add(counter_cache_key, 1, counter_cache_ttl)

    def add_to_cached_ids(current_ids: set | None):
        if current_ids is None:
            current_ids = set()

        if pk not in current_ids:
            current_ids.add(pk)

        return current_ids

    set_cache_with_lock(ELIST_NUM_ENTITIES_IDS, add_to_cached_ids, counter_cache_ttl)
    cache.add(ELIST_NUM_ENTITIES_CREATED_AT, timezone.now(), counter_cache_ttl)

    if not counter_cache_created:
        cache.incr(counter_cache_key)


def _dec_elist_num_entities_cache(pk: int) -> None:
    """Decrement EntityList `num_entities` counter in cache

    Args:
        pk (int): Primary key for EntityList
    """
    counter_cache_key = f"{ELIST_NUM_ENTITIES}{pk}"

    if cache.get(counter_cache_key) is not None:
        cache.decr(counter_cache_key)


def inc_elist_num_entities(pk: int) -> None:
    """Increment EntityList `num_entities` counter

    Updates cached counter if cache is not locked. Else, the database
    counter is updated

    Args:
        pk (int): Primary key for EntityList
    """

    if _is_elist_num_entities_cache_locked():
        _inc_elist_num_entities_db(pk)

    else:
        try:
            _inc_elist_num_entities_cache(pk)
            _exec_cached_elist_counter_commit_failover()

        except ConnectionError as exc:
            logger.exception(exc)
            # Fallback to db if cache inacessible
            _inc_elist_num_entities_db(pk)


def dec_elist_num_entities(pk: int) -> None:
    """Decrement EntityList `num_entities` counter

    Updates cached counter if cache is not locked. Else, the database
    counter is updated.

    Args:
        pk (int): Primary key for EntityList
    """
    counter_cache_key = f"{ELIST_NUM_ENTITIES}{pk}"

    if _is_elist_num_entities_cache_locked() or cache.get(counter_cache_key) is None:
        _dec_elist_num_entities_db(pk)

    else:
        try:
            _dec_elist_num_entities_cache(pk)

        except ConnectionError as exc:
            logger.exception(exc)
            # Fallback to db if cache inacessible
            _dec_elist_num_entities_db(pk)


def _is_elist_num_entities_cache_locked() -> bool:
    """Checks if EntityList `num_entities` cached counter is locked

    Typically, the cache is locked if the cached data is in the process
    of being persisted in the database.

    The cache is locked to ensure no further updates are made when the
    data is being committed to the database.

    Returns True, if cache is locked, False otherwise
    """

    return cache.get(ELIST_NUM_ENTITIES_LOCK) is not None


def commit_cached_elist_num_entities() -> None:
    """Commit cached EntityList `num_entities` counter to the database

    Commit is successful if no other process holds the lock
    """
    lock_acquired = cache.add(ELIST_NUM_ENTITIES_LOCK, "true", 7200)

    if lock_acquired:
        entity_list_pks: set[int] = cache.get(ELIST_NUM_ENTITIES_IDS, set())

        for pk in entity_list_pks:
            counter_key = f"{ELIST_NUM_ENTITIES}{pk}"
            counter: int = cache.get(counter_key, 0)

            if counter:
                _inc_elist_num_entities_db(pk, counter)

            safe_delete(counter_key)

        safe_delete(ELIST_NUM_ENTITIES_IDS)
        safe_delete(ELIST_NUM_ENTITIES_LOCK)
        safe_delete(ELIST_NUM_ENTITIES_CREATED_AT)


def _exec_cached_elist_counter_commit_failover() -> None:
    """Check the time lapse since the cached EntityList `num_entities`
    counters were created and commit if the time lapse exceeds
    the threshold allowed.

    Acts as a failover incase the cron job responsible for committing
    the cached data fails or is not configured
    """
    cache_created_at: datetime | None = cache.get(ELIST_NUM_ENTITIES_CREATED_AT)

    if cache_created_at is None:
        return

    # If the time lapse is > ELIST_COUNTER_COMMIT_FAILOVER_TIMEOUT, run the failover
    failover_timeout: int = getattr(
        settings, "ELIST_COUNTER_COMMIT_FAILOVER_TIMEOUT", 7200
    )
    time_lapse = timezone.now() - cache_created_at

    if time_lapse.total_seconds() > failover_timeout:
        commit_cached_elist_num_entities()
        # Do not send report exception if already sent within the past 24 hrs
        if cache.get(ELIST_FAILOVER_REPORT_SENT) is None:
            subject = "Periodic task not running"
            task_name = (
                "onadata.apps.logger.tasks.commit_cached_elist_num_entities_async"
            )
            msg = (
                f"The failover has been executed because task {task_name} "
                "is not configured or has malfunctioned"
            )
            report_exception(subject, msg)
            cache.set(ELIST_FAILOVER_REPORT_SENT, "sent", 86400)


def delete_xform_submissions(
    xform: XForm,
    deleted_by: User,
    instance_ids: list[int] | None = None,
    soft_delete: bool = True,
) -> None:
    """ "Delete subset or all submissions of an XForm

    :param xform: XForm object
    :param deleted_by: User initiating the delete
    :param instance_ids: List of instance ids to delete, None to delete all
    :param soft_delete: Flag to soft delete or hard delete
    :return: None
    """
    if not soft_delete and not getattr(
        settings, "ENABLE_SUBMISSION_PERMANENT_DELETE", False
    ):
        raise PermissionDenied("Hard delete is not enabled")

    instance_qs = xform.instances.filter(deleted_at__isnull=True)

    if instance_ids:
        instance_qs = instance_qs.filter(id__in=instance_ids)

    if soft_delete:
        now = timezone.now()
        instance_qs.update(deleted_at=now, date_modified=now, deleted_by=deleted_by)
    else:
        # Hard delete
        instance_qs.delete()

    if instance_ids is None:
        # Every submission has been deleted
        xform.num_of_submissions = 0
        xform.save(update_fields=["num_of_submissions"])

    else:
        xform.submission_count(force_update=True)

    xform.project.date_modified = timezone.now()
    xform.project.save(update_fields=["date_modified"])
    safe_delete(f"{XFORM_SUBMISSIONS_DELETING}{xform.pk}")
    send_message(
        instance_id=instance_ids,
        target_id=xform.id,
        target_type=XFORM,
        user=deleted_by,
        message_verb=SUBMISSION_DELETED,
    )


def _register_instance_repeat_columns(instance: Instance, register: MetaData) -> None:
    """Add Instance repeat columns to the export columns register

    :param instance: Instance object
    :param metadata: MetaData object that stores the export repeat register
    """
    # Avoid cyclic import by using importlib
    csv_builder_module = importlib.import_module("onadata.libs.utils.csv_builder")

    with transaction.atomic():
        # We use select_for_update to acquire a row-level lock
        # Only one process updates it at a time. This prevents race conditions
        # and updates extra_data atomically
        register = MetaData.objects.select_for_update().get(pk=register.pk)
        merged_multiples = json.loads(
            register.extra_data["merged_multiples"], object_pairs_hook=OrderedDict
        )
        split_multiples = json.loads(
            register.extra_data["split_multiples"], object_pairs_hook=OrderedDict
        )
        xform = instance.xform
        csv_builder_module = csv_builder_module.CSVDataFrameBuilder(
            xform=xform, username=xform.user.username, id_string=xform.id_string
        )
        data = instance.get_full_dict()
        changes = {
            "merged_multiples": merged_multiples,
            "split_multiples": split_multiples,
        }

        for key, value in data.items():
            # Reindex split multiples
            # pylint: disable=protected-access
            csv_builder_module._reindex(
                key,
                value,
                changes["split_multiples"],
                data,
                xform,
                include_images=[],
                split_select_multiples=True,
            )
            # Reindex merged multiples
            # pylint: disable=protected-access
            csv_builder_module._reindex(
                key,
                value,
                changes["merged_multiples"],
                data,
                xform,
                include_images=[],
                split_select_multiples=False,
            )

        register.extra_data = {key: json.dumps(value) for key, value in changes.items()}
        register.save()


@transaction.atomic()
def register_instance_repeat_columns(instance: Instance) -> None:
    """Add an Instance repeat columns to the export columns register

    :param instance: Instance object
    """
    content_type = ContentType.objects.get_for_model(instance.xform)

    try:
        register = MetaData.objects.get(
            content_type=content_type,
            object_id=instance.xform.pk,
            data_type=EXPORT_COLUMNS_REGISTER,
        )

    except MetaData.DoesNotExist:
        return

    _register_instance_repeat_columns(instance, register)


@transaction.atomic()
def reconstruct_xform_export_register(xform: XForm) -> None:
    """Reconstruct the export columns register for an XForm

    :param xform: XForm object
    """
    try:
        register = MetaData.objects.get(
            content_type=ContentType.objects.get_for_model(xform),
            object_id=xform.pk,
            data_type=EXPORT_COLUMNS_REGISTER,
        )

    except MetaData.DoesNotExist:
        return

    instance_qs = xform.instances.filter(deleted_at__isnull=True)

    for instance in queryset_iterator(instance_qs, chunksize=500):
        _register_instance_repeat_columns(instance, register)
