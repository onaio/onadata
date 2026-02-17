"""
Key management utility functions
"""

import importlib
import logging
import mimetypes
import os
from contextlib import suppress
from datetime import timedelta
from hashlib import sha256
from io import BytesIO

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import File
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from valigetta.decryptor import decrypt_submission
from valigetta.exceptions import (
    AliasAlreadyExistsException,
    CreateAliasException,
    GetPublicKeyException,
    InvalidSubmissionException,
)
from valigetta.kms import APIKMSClient as BaseAPIClient
from valigetta.kms import AWSKMSClient as BaseAWSClient

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.logger.models import (
    Instance,
    InstanceHistory,
    KMSKey,
    XForm,
    XFormKey,
)
from onadata.libs.exceptions import (
    DecryptionError,
    EncryptionError,
    NotAllMediaReceivedError,
)
from onadata.libs.permissions import is_organization
from onadata.libs.utils.cache_tools import (
    XFORM_DEC_SUBMISSION_COUNT,
    XFORM_DEC_SUBMISSION_COUNT_CREATED_AT,
    XFORM_DEC_SUBMISSION_COUNT_FAILOVER_REPORT_SENT,
    XFORM_DEC_SUBMISSION_COUNT_IDS,
    XFORM_DEC_SUBMISSION_COUNT_LOCK,
)
from onadata.libs.utils.common_tags import (
    DECRYPTION_ERROR,
    DECRYPTION_FAILURE_ENCRYPTION_UNMANAGED,
    DECRYPTION_FAILURE_INSTANCE_NOT_ENCRYPTED,
    DECRYPTION_FAILURE_INVALID_SUBMISSION,
    DECRYPTION_FAILURE_KEY_DISABLED,
    DECRYPTION_FAILURE_KEY_NOT_FOUND,
    DECRYPTION_FAILURE_MESSAGES,
    DECRYPTION_FAILURE_NOT_ALL_MEDIA_RECEIVED,
)
from onadata.libs.utils.email import friendly_date, send_mass_mail
from onadata.libs.utils.logger_tools import create_xform_version
from onadata.libs.utils.model_tools import (
    adjust_counter,
    commit_cached_counters,
    queryset_iterator,
    update_fields_directly,
)

logger = logging.getLogger(__name__)


def _get_kms_client_class():
    """Return the KMS client that is active."""
    class_path = getattr(
        settings, "KMS_CLIENT_CLASS", "onadata.libs.kms.clients.AWSKMSClient"
    )

    if not class_path:
        raise ImproperlyConfigured("KMS_CLIENT_CLASS setting is not defined.")

    try:
        return import_string(class_path)
    except ImportError as exc:
        raise ImproperlyConfigured(
            f"Could not import KMS_CLIENT_CLASS '{class_path}': {exc}"
        ) from exc


def _get_kms_rotation_duration():
    duration = getattr(settings, "KMS_ROTATION_DURATION", None)

    if isinstance(duration, timedelta):
        return duration

    if duration:
        logger.error("KMS_ROTATION_DURATION is set to an invalid value: %s", duration)

    return None


def _get_kms_grace_period_duration():
    default_duration = timedelta(days=30)
    duration = getattr(settings, "KMS_GRACE_PERIOD_DURATION", default_duration)

    if isinstance(duration, timedelta):
        return duration

    if duration:
        logger.error(
            "KMS_GRACE_PERIOD_DURATION is set to an invalid value: %s",
            duration,
        )

    return default_duration


def _get_kms_rotation_reminder_duration():
    default_duration = timedelta(weeks=2)
    duration = getattr(settings, "KMS_ROTATION_REMINDER_DURATION", default_duration)

    if isinstance(duration, timedelta):
        return duration

    if duration:
        logger.error(
            "KMS_ROTATION_REMINDER_DURATION is set to an invalid value: %s",
            duration,
        )

    return default_duration


def _get_kms_grace_expiry_reminder_duration():
    default_duration = timedelta(days=1)
    duration = getattr(settings, "KMS_GRACE_EXPIRY_REMINDER_DURATION", default_duration)

    if isinstance(duration, timedelta):
        return duration

    if isinstance(duration, list) and all(
        isinstance(item, timedelta) for item in duration
    ):
        return duration

    if duration:
        logger.error(
            "KMS_GRACE_EXPIRY_REMINDER_DURATION is set to an invalid value: %s",
            duration,
        )

    return default_duration


def get_kms_client():
    """Retrieve the appropriate KMS client based on settings."""
    kms_client_cls = _get_kms_client_class()

    return kms_client_cls()


def clean_public_key(value):
    """
    Strips public key headers, footers, spaces, and newlines.
    """
    header = "-----BEGIN PUBLIC KEY-----"
    footer = "-----END PUBLIC KEY-----"

    value = value.strip()

    if value.startswith(header) and value.endswith(footer):
        return value.replace(header, "").replace(footer, "").replace(" ", "").strip()

    return value


def _invalidate_organization_cache(org: OrganizationProfile):
    """Invalidate organization cache.

    :param org: Organization
    """
    # Avoid circular import
    api_tools = importlib.import_module("onadata.apps.api.tools")
    api_tools.invalidate_organization_cache(org.user.username)


# pylint: disable=too-many-locals
@transaction.atomic()
def create_key(org: OrganizationProfile, created_by=None) -> KMSKey:
    """Create KMS key.

    :param org: Organization that owns the key
    :param created_by: User creating the key
    :return: KMSKey
    """
    kms_client = get_kms_client()
    now = timezone.now()
    description = f"Key-{now.strftime('%Y-%m-%d')}"
    content_type = ContentType.objects.get_for_model(org)
    duplicate_desc = KMSKey.objects.filter(
        content_type=content_type,
        object_id=org.pk,
        description__startswith=description,
    )

    if duplicate_desc.exists():
        suffix = f"-v{duplicate_desc.count() + 1}"
        description += suffix

    kms_description = description

    if created_by is None:
        kms_description += _(" via automatic rotation")

    else:
        kms_description += _(" via manual rotation")

    metadata = kms_client.create_key(description=kms_description)
    key_id = metadata["key_id"]
    deployment_name = getattr(settings, "DEPLOYMENT_NAME", "Ona")
    alias_name = f"alias/{deployment_name}/{org.user.username}/{description}"

    try:
        public_key = kms_client.get_public_key(key_id)

        with suppress(AliasAlreadyExistsException):
            kms_client.create_alias(alias_name=alias_name, key_id=key_id)

    except (GetPublicKeyException, CreateAliasException) as exc:
        logger.exception(exc)
        # Disable key to avoid orphan keys (active keys not
        # assigned to an organization)
        kms_client.disable_key(key_id)

        raise

    rotation_duration = _get_kms_rotation_duration()
    expiry_date = None

    if rotation_duration:
        expiry_date = now + rotation_duration

    provider = None

    if isinstance(kms_client, BaseAWSClient):
        provider = KMSKey.KMSProvider.AWS
    elif isinstance(kms_client, BaseAPIClient):
        provider = KMSKey.KMSProvider.API

    kms_key = KMSKey.objects.create(
        key_id=key_id,
        description=description,
        public_key=clean_public_key(public_key),
        provider=provider,
        expiry_date=expiry_date,
        content_type=content_type,
        object_id=org.pk,
        created_by=created_by,
        is_active=True,
    )

    try:
        # Invalidate cache for organization profile endpoint
        _invalidate_organization_cache(org)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Catch exception to avoid transaction rollback
        logger.exception(exc)

    return kms_key


@transaction.atomic()
def disable_key(kms_key: KMSKey, disabled_by=None) -> None:
    """Disable KMS key.

    :param kms_key: KMSKey
    :param disabled_by: User disabling the key
    """
    if kms_key.disabled_at:
        return

    kms_client = get_kms_client()
    kms_client.disable_key(kms_key.key_id)
    kms_key.disabled_at = timezone.now()
    kms_key.disabled_by = disabled_by
    kms_key.is_active = False
    kms_key.save(update_fields=["disabled_at", "disabled_by", "is_active"])

    try:
        # Invalidate cache for organization profile endpoint
        _invalidate_organization_cache(kms_key.content_object)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Catch exception to avoid transaction rollback
        logger.exception(exc)


def _invalidate_xform_list_cache(xform: XForm):
    """Invalidate XForm list cache.

    :param xform: XForm
    """
    # Avoid circular import
    api_tools = importlib.import_module("onadata.apps.api.tools")
    api_tools.invalidate_xform_list_cache(xform)


def _encrypt_xform(xform, kms_key, encrypted_by=None):
    version = timezone.now().strftime("%Y%m%d%H%M")

    survey, workbook_json = xform.get_survey_and_json_from_xlsform()
    survey.public_key = kms_key.public_key
    survey.version = version
    # Update cached survey for _set_encrypted_field()
    xform.set_survey(survey)

    workbook_json["public_key"] = kms_key.public_key
    workbook_json["version"] = version
    xform.json = workbook_json
    xform.xml = survey.to_xml()
    xform.version = version
    xform.public_key = kms_key.public_key
    xform.encrypted = True
    xform.is_managed = True
    xform.hash = xform.get_hash()
    xform.save()
    xform.kms_keys.create(version=version, kms_key=kms_key, encrypted_by=encrypted_by)

    try:
        # Create a XFormVersion of new version
        create_xform_version(xform, encrypted_by)
        # Invalidate cache for formList endpoint
        _invalidate_xform_list_cache(xform)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Catch exception to avoid transaction rollback
        logger.exception(exc)


@transaction.atomic()
def rotate_key(kms_key: KMSKey, rotated_by=None, rotation_reason=None) -> KMSKey:
    """Rotate KMS key.

    :param kms_key: KMSKey to be rotated
    :param rotated_by: User rotating the key
    :param rotation_reason: Reason for rotation
    :return: New KMSKey
    """

    def send_email_notification(organization):
        recipient_list = _get_org_owners_emails(organization)

        if not recipient_list:
            return

        mail_subject = _(f"Key Rotated for Organization: {organization.name}")
        message = render_to_string(
            "organization/key_rotated.html",
            {
                "organization_name": organization.name,
                "grace_end_date": friendly_date(kms_key.grace_end_date),
                "deployment_name": getattr(settings, "DEPLOYMENT_NAME", "Ona"),
            },
        )
        send_mail(
            mail_subject,
            strip_tags(message),
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            html_message=message,
        )

    if kms_key.disabled_at:
        raise EncryptionError("Key is disabled.")

    if kms_key.rotated_at:
        raise EncryptionError("Key already rotated.")

    organization = kms_key.content_object
    new_key = create_key(organization, created_by=rotated_by)

    # Update XForms using the old key to use the new key
    xform_qs = XForm.objects.filter(
        pk__in=kms_key.xforms.values_list("xform_id", flat=True).distinct()
    )

    for xform in queryset_iterator(xform_qs):
        _encrypt_xform(xform=xform, kms_key=new_key, encrypted_by=rotated_by)

    # If the rotation is pre-mature, force expiry
    kms_key.expiry_date = min(kms_key.expiry_date, timezone.now())
    kms_key.grace_end_date = kms_key.expiry_date + _get_kms_grace_period_duration()
    kms_key.rotated_at = timezone.now()
    kms_key.rotated_by = rotated_by
    kms_key.rotation_reason = rotation_reason
    kms_key.is_active = False
    kms_key.save(
        update_fields=[
            "expiry_date",
            "grace_end_date",
            "rotated_at",
            "rotated_by",
            "rotation_reason",
            "is_active",
        ]
    )

    try:
        # Invalidate cache for organization profile endpoint
        _invalidate_organization_cache(organization)
        # Send email notification
        send_email_notification(organization)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Catch exception to avoid transaction rollback
        logger.exception(exc)

    return new_key


@transaction.atomic()
def encrypt_xform(xform, encrypted_by=None, override_encryption=False) -> None:
    """Encrypt unencrypted XForm

    :param xform: Unencrypted XForm
    :param encrypted_by: User encrypting the form
    :param override_encryption: Whether to override encryption
    """
    if xform.encrypted and not override_encryption:
        return

    if xform.num_of_submissions:
        raise EncryptionError("XForm already has submissions.")

    user_profile = xform.user.profile

    if not is_organization(user_profile):
        raise EncryptionError("XForm owner is not an organization user.")

    org = user_profile.organizationprofile
    content_type = ContentType.objects.get_for_model(OrganizationProfile)
    kms_key_qs = KMSKey.objects.filter(
        object_id=org.pk, content_type=content_type, is_active=True
    )

    if not kms_key_qs.exists():
        raise EncryptionError("No encryption key found for the organization.")

    kms_key = kms_key_qs.first()

    _encrypt_xform(xform=xform, kms_key=kms_key, encrypted_by=encrypted_by)


def save_decryption_error(instance: Instance, error_name: str):
    """Add decryption error metadata to Instance json.

    :param instance: Instance
    :param error_name: Error code
    """
    # Create a copy that we'll mutate
    json = dict(instance.json or {})
    json[DECRYPTION_ERROR] = error_name
    update_fields_directly(
        instance,
        json=json,
        decryption_status=Instance.DecryptionStatus.FAILED,
    )


# pylint: disable=too-many-locals,too-many-statements
def decrypt_instance(instance: Instance) -> None:
    """Decrypt encrypted Instance

    :param instance: Instance to be decrypted
    """
    # Avoid cyclic dependency errors
    logger_tasks = importlib.import_module("onadata.apps.logger.tasks")
    incr_task = logger_tasks.adjust_xform_num_of_decrypted_submissions_async

    def get_encrypted_files(attachment_qs):
        """Get Instance's encrypted media files"""
        enc_files = {}

        for attachment in queryset_iterator(attachment_qs):
            name = attachment.name or attachment.media_file.name.split("/")[-1]

            with attachment.media_file.open("rb") as file:
                enc_files[name] = BytesIO(file.read())

        return enc_files

    if not instance.check_encrypted():
        raise DecryptionError(
            DECRYPTION_FAILURE_MESSAGES[DECRYPTION_FAILURE_INSTANCE_NOT_ENCRYPTED]
        )

    if not instance.xform.is_was_managed:
        raise DecryptionError(
            DECRYPTION_FAILURE_MESSAGES[DECRYPTION_FAILURE_ENCRYPTION_UNMANAGED]
        )

    try:
        # Get the key that encrypted the submission
        xform_key = XFormKey.objects.get(version=instance.version, xform=instance.xform)

    except XFormKey.DoesNotExist as exc:
        save_decryption_error(instance, DECRYPTION_FAILURE_KEY_NOT_FOUND)
        raise DecryptionError(
            DECRYPTION_FAILURE_MESSAGES[DECRYPTION_FAILURE_KEY_NOT_FOUND]
        ) from exc

    if xform_key.kms_key.disabled_at is not None:
        save_decryption_error(instance, DECRYPTION_FAILURE_KEY_DISABLED)
        raise DecryptionError(
            DECRYPTION_FAILURE_MESSAGES[DECRYPTION_FAILURE_KEY_DISABLED]
        )

    if not instance.media_all_received:
        save_decryption_error(instance, DECRYPTION_FAILURE_NOT_ALL_MEDIA_RECEIVED)
        raise NotAllMediaReceivedError(
            DECRYPTION_FAILURE_MESSAGES[DECRYPTION_FAILURE_NOT_ALL_MEDIA_RECEIVED]
        )

    submission_xml = BytesIO(instance.xml.encode("utf-8"))
    kms_client = get_kms_client()
    # Decrypt submission files
    attachment_qs = instance.attachments.filter(deleted_at__isnull=True)
    decrypted_files = decrypt_submission(
        kms_client=kms_client,
        key_id=xform_key.kms_key.key_id,
        submission_xml=submission_xml,
        enc_files=get_encrypted_files(attachment_qs),
    )
    # Replace encrypted submission with decrypted submission
    # Check if this is an edit (has prior history) before creating new history
    is_edit = instance.submission_history.exists()
    # Initialize InstanceHistory before replacement
    history = InstanceHistory(
        checksum=instance.checksum,
        xml=instance.xml,
        xform_instance=instance,
        uuid=instance.uuid,
        geom=instance.geom,
        submission_date=instance.last_edited or instance.date_created,
    )
    decrypted_attachment_ids = []

    try:
        with transaction.atomic():
            for original_name, decrypted_file in decrypted_files:
                if original_name.lower() == "submission.xml":
                    # Replace submission with decrypted submission
                    xml = decrypted_file.getvalue()

                    instance.xml = xml.decode("utf-8")
                    instance.checksum = sha256(xml).hexdigest()
                    instance.is_encrypted = False
                    instance.decryption_status = Instance.DecryptionStatus.SUCCESS
                    instance.save()

                else:
                    # Save decrypted media file
                    media_file = File(decrypted_file, name=original_name)
                    mimetype, _ = mimetypes.guess_type(original_name)
                    _, extension = os.path.splitext(original_name)
                    attachment = instance.attachments.create(
                        xform=instance.xform,
                        media_file=media_file,
                        name=original_name,
                        mimetype=mimetype or "application/octet-stream",
                        extension=extension.lstrip("."),
                        file_size=len(decrypted_file.getbuffer()),
                    )
                    decrypted_attachment_ids.append(attachment.id)

            # Commit history after saving decrypted files
            history.save()
            # Soft delete encrypted attachments
            attachment_qs.exclude(id__in=decrypted_attachment_ids).update(
                deleted_at=timezone.now()
            )
            # Increment XForm num_of_decrypted_submissions only for new
            # submissions
            if not is_edit:
                transaction.on_commit(
                    lambda: incr_task.delay(instance.xform_id, delta=1)
                )

    except InvalidSubmissionException as exc:
        save_decryption_error(instance, DECRYPTION_FAILURE_INVALID_SUBMISSION)
        raise DecryptionError(str(exc)) from exc


@transaction.atomic()
def disable_xform_encryption(xform, disabled_by=None) -> None:
    """Disable encryption on encrypted XForm

    :param xform: XForm to disable encryption
    :param disabled_by: User disabling encryption
    """
    if not xform.encrypted:
        return

    if xform.num_of_submissions:
        raise EncryptionError("XForm already has submissions.")

    xform_key_qs = xform.kms_keys.filter(version=xform.version)

    # XForm should be encrypted using managed keys
    if not xform_key_qs.exists():
        raise EncryptionError("XForm encryption is not via managed keys.")

    new_version = timezone.now().strftime("%Y%m%d%H%M")

    survey, workbook_json = xform.get_survey_and_json_from_xlsform()
    survey.public_key = None
    survey.version = new_version
    # Update cached survey for _set_encrypted_field()
    xform.set_survey(survey)

    workbook_json.pop("public_key", None)
    workbook_json["version"] = new_version
    xform.json = workbook_json
    xform.xml = survey.to_xml()
    xform.version = new_version
    xform.public_key = None
    xform.encrypted = False
    xform.is_managed = False
    xform.hash = xform.get_hash()
    xform.save()

    try:
        # Create XFormVersion of new version
        create_xform_version(xform, disabled_by)
        # Invalidate cache for formList endpoint
        _invalidate_xform_list_cache(xform)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Catch exceptions to avoid transaction rollback
        logger.exception(exc)


def _get_org_owners_emails(organization: OrganizationProfile) -> list[str]:
    """Get organization owners emails

    :param organization: Organization
    """
    api_tools = importlib.import_module("onadata.apps.api.tools")
    return [owner.email for owner in api_tools.get_organization_owners(organization)]


def send_key_rotation_reminder():
    """Send email to organization admins that key rotation is scheduled."""
    notification_duration = _get_kms_rotation_reminder_duration()
    target_date = (timezone.now() + notification_duration).date()
    kms_key_qs = KMSKey.objects.filter(
        expiry_date__date=target_date,
        disabled_at__isnull=True,
        rotated_at__isnull=True,
    )
    mass_mail_data = []

    for kms_key in queryset_iterator(kms_key_qs):
        organization = kms_key.content_object
        recipient_list = _get_org_owners_emails(organization)

        if not recipient_list:
            continue

        mail_subject = _(f"Key Rotation for Organization: {organization.name}")
        grace_end_date = kms_key.expiry_date + _get_kms_grace_period_duration()
        message = render_to_string(
            "organization/key_rotation_reminder.html",
            {
                "organization_name": organization.name,
                "rotation_date": friendly_date(kms_key.expiry_date),
                "grace_end_date": friendly_date(grace_end_date),
                "deployment_name": getattr(settings, "DEPLOYMENT_NAME", "Ona"),
            },
        )
        mass_mail_data.append(
            (
                mail_subject,
                strip_tags(message),
                message,
                settings.DEFAULT_FROM_EMAIL,
                recipient_list,
            )
        )

    if mass_mail_data:
        send_mass_mail(tuple(mass_mail_data))


def send_key_grace_expiry_reminder():
    """Send email to organization admins that key grace period is scheduled."""
    now = timezone.now()
    notification_duration = _get_kms_grace_expiry_reminder_duration()
    target_dates = []

    if isinstance(notification_duration, timedelta):
        target_dates = [(now + notification_duration).date()]

    elif isinstance(notification_duration, list):
        target_dates = [(now + duration).date() for duration in notification_duration]

    # Any non-disabled key with a grace period date
    kms_key_qs = KMSKey.objects.filter(
        grace_end_date__date__in=target_dates,
        disabled_at__isnull=True,
    )
    mass_mail_data = []

    for kms_key in queryset_iterator(kms_key_qs):
        organization = kms_key.content_object
        recipient_list = _get_org_owners_emails(organization)

        if not recipient_list:
            continue

        mail_subject = _(
            f"Key Grace Period Expiry for Organization: {organization.name}"
        )
        message = render_to_string(
            "organization/key_grace_expiry_reminder.html",
            {
                "organization_name": organization.name,
                "grace_end_date": friendly_date(kms_key.grace_end_date),
                "deployment_name": getattr(settings, "DEPLOYMENT_NAME", "Ona"),
            },
        )
        mass_mail_data.append(
            (
                mail_subject,
                strip_tags(message),
                message,
                settings.DEFAULT_FROM_EMAIL,
                recipient_list,
            )
        )

    if mass_mail_data:
        send_mass_mail(tuple(mass_mail_data))


def rotate_expired_keys():
    """Rotate expired keys."""
    kms_key_qs = KMSKey.objects.filter(
        expiry_date__lte=timezone.now(),
        disabled_at__isnull=True,
        rotated_at__isnull=True,
    )

    for kms_key in queryset_iterator(kms_key_qs):
        try:
            rotate_key(kms_key)
        except EncryptionError:
            logger.exception("Key rotation failed for key %s", kms_key.key_id)


def disable_expired_keys():
    """Disable expired keys whose grace period has expired."""
    now = timezone.now()
    kms_key_qs = KMSKey.objects.filter(
        expiry_date__lte=now,
        grace_end_date__lte=now,
        disabled_at__isnull=True,
    )
    mass_mail_data = []

    for kms_key in queryset_iterator(kms_key_qs):
        try:
            disable_key(kms_key)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Key disable failed for key %s", kms_key.key_id)
            continue

        if not kms_key.rotated_at:
            continue

        # Send notification to organization admins
        organization = kms_key.content_object
        recipient_list = _get_org_owners_emails(organization)

        if not recipient_list:
            continue

        mail_subject = _(
            f"Key Rotation Completed for Organization: {organization.name}"
        )
        message = render_to_string(
            "organization/key_rotation_completed.html",
            {
                "organization_name": organization.name,
                "deployment_name": getattr(settings, "DEPLOYMENT_NAME", "Ona"),
            },
        )
        mass_mail_data.append(
            (
                mail_subject,
                strip_tags(message),
                message,
                settings.DEFAULT_FROM_EMAIL,
                recipient_list,
            )
        )

    if mass_mail_data:
        send_mass_mail(tuple(mass_mail_data))


def adjust_xform_num_of_decrypted_submissions(xform: XForm, delta: int) -> None:
    """Adjust XForm `num_of_decrypted_submissions` counter

    :param xform: XForm
    :param delta: Value to increment or decrement by
    """
    # Ignore XForm that is not managed using encryption keys
    if not xform.is_managed:
        return

    adjust_counter(
        pk=xform.pk,
        model=XForm,
        field_name="num_of_decrypted_submissions",
        delta=delta,
        key_prefix=XFORM_DEC_SUBMISSION_COUNT,
        tracked_ids_key=XFORM_DEC_SUBMISSION_COUNT_IDS,
        created_at_key=XFORM_DEC_SUBMISSION_COUNT_CREATED_AT,
        lock_key=XFORM_DEC_SUBMISSION_COUNT_LOCK,
        failover_report_key=XFORM_DEC_SUBMISSION_COUNT_FAILOVER_REPORT_SENT,
        task_name=(
            "onadata.apps.logger.tasks"
            ".commit_cached_xform_num_of_decrypted_submissions_async"
        ),
    )


def commit_cached_xform_num_of_decrypted_submissions():
    """Commit cached XForm `num_of_decrypted_submissions` counter to the database"""
    commit_cached_counters(
        model=XForm,
        field_name="num_of_decrypted_submissions",
        key_prefix=XFORM_DEC_SUBMISSION_COUNT,
        tracked_ids_key=XFORM_DEC_SUBMISSION_COUNT_IDS,
        lock_key=XFORM_DEC_SUBMISSION_COUNT_LOCK,
        created_at_key=XFORM_DEC_SUBMISSION_COUNT_CREATED_AT,
    )
