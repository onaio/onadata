"""
Key management utility functions
"""

import logging
import mimetypes
import os
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
from xml.etree import ElementTree

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import File
from django.db import transaction
from django.utils import timezone

from valigetta.decryptor import extract_encrypted_submission_file_name
from valigetta.exceptions import InvalidSubmission

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.logger.models import Instance, InstanceHistory, KMSKey, XFormKey
from onadata.apps.logger.models.xform import create_survey_element_from_dict
from onadata.libs.exceptions import EncryptionError
from onadata.libs.kms.clients import AWSKMSClient
from onadata.libs.permissions import is_organization
from onadata.libs.utils.logger_tools import create_xform_version
from onadata.libs.utils.model_tools import queryset_iterator

logger = logging.getLogger(__name__)

KMS_CLIENTS = {"AWS": AWSKMSClient}


def _get_kms_provider():
    return getattr(settings, "KMS_PROVIDER", "AWS")


def get_kms_client():
    """Retrieve the appropriate KMS client based on settings."""
    kms_provider = _get_kms_provider()
    kms_client_cls = KMS_CLIENTS.get(kms_provider)

    if not kms_client_cls:
        raise ImproperlyConfigured(f"Unsupported KMS provider: {kms_provider}")

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


def create_key(org: OrganizationProfile) -> KMSKey:
    """Create KMS key.

    :param org: Organization that owns the key
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

    metadata = kms_client.create_key(description=description)
    expiry_date = None

    if hasattr(settings, "KMS_ROTATION_DURATION") and isinstance(
        settings.KMS_ROTATION_DURATION, timedelta
    ):
        expiry_date = now + settings.KMS_ROTATION_DURATION

    provider_choice_map = {
        "AWS": KMSKey.KMSProvider.AWS,
    }
    provider = provider_choice_map.get(_get_kms_provider().upper())

    return KMSKey.objects.create(
        key_id=metadata["key_id"],
        description=description,
        public_key=clean_public_key(metadata["public_key"]),
        provider=provider,
        expiry_date=expiry_date,
        content_type=content_type,
        object_id=org.pk,
    )


def disable_key(kms_key: KMSKey, disabled_by=None) -> None:
    """Disable KMS key.

    :param kms_key: KMSKey
    :parem disabled_by: User disabling the key
    """
    kms_client = get_kms_client()
    kms_client.disable_key(kms_key.key_id)
    kms_key.disabled_at = timezone.now()
    kms_key.disabled_by = disabled_by
    kms_key.save(update_fields=["disabled_at", "disabled_by"])


def _encrypt_xform(xform, kms_key, encrypted_by=None):
    version = timezone.now().strftime("%Y%m%d%H%M")

    json_dict = xform.json_dict()
    json_dict["public_key"] = kms_key.public_key
    json_dict["version"] = version

    survey = create_survey_element_from_dict(json_dict)

    xform.json = survey.to_json_dict()
    xform.xml = survey.to_xml()
    xform.version = version
    xform.public_key = kms_key.public_key
    xform.encrypted = True
    xform.save()
    xform.kms_keys.create(version=version, kms_key=kms_key, encrypted_by=encrypted_by)


@transaction.atomic()
def rotate_key(kms_key: KMSKey, rotated_by=None) -> KMSKey:
    """Rotate KMS key.

    :param kms_key: KMSKey
    :return: New KMSKey
    """
    new_key = create_key(kms_key.content_object)

    # Update forms using the old key to use the new key
    xform_key_qs = kms_key.xforms.all()

    for xform_key in queryset_iterator(xform_key_qs):
        _encrypt_xform(xform=xform_key.xform, kms_key=new_key, encrypted_by=rotated_by)

    return new_key


@transaction.atomic()
def encrypt_xform(xform, encrypted_by=None) -> None:
    """Encrypt unencrypted XForm

    :param xform: Unencrypted XForm
    :param encrypted_by: User encrypting the form
    """
    if xform.encrypted:
        return

    if xform.num_of_submissions:
        raise EncryptionError("XForm already has submissions.")

    user_profile = xform.user.profile

    if not is_organization(user_profile):
        raise EncryptionError("XForm owner is not an organization user.")

    org = user_profile.organizationprofile
    content_type = ContentType.objects.get_for_model(OrganizationProfile)
    kms_key_qs = KMSKey.objects.filter(
        object_id=org.pk, content_type=content_type, disabled_at__isnull=True
    ).order_by("-date_created")

    if not kms_key_qs:
        raise EncryptionError("No encryption key found for the organization.")

    kms_key = kms_key_qs.first()

    _encrypt_xform(xform=xform, kms_key=kms_key, encrypted_by=encrypted_by)


def is_instance_encrypted(instance):
    """Return True if instance is encrypted

    :param instance: Instance
    """

    submission_xml = BytesIO(instance.xml.encode("utf-8"))

    try:
        tree = ElementTree.fromstring(submission_xml.read())
        extract_encrypted_submission_file_name(tree)

    except InvalidSubmission:
        return False

    return True


@transaction.atomic()
def decrypt_instance(instance: Instance):
    """Decrypt encrypted Instance

    :param instance: Instance to be decrypted
    """
    if not is_instance_encrypted(instance):
        return

    submission_xml = BytesIO(instance.xml.encode("utf-8"))
    kms_client = get_kms_client()
    # Get the key that encrypted the submission
    xms_key = XFormKey.objects.get(version=instance.version, xform=instance.xform)
    # Decrypt submission files
    attachment_qs = instance.attachments.all()

    def get_encrypted_files():
        enc_files = {}

        for attachment in queryset_iterator(attachment_qs):
            name = attachment.name or attachment.media_file.name.split("/")[-1]

            with attachment.media_file.open("rb") as file:
                enc_files[name] = file.read()

        return enc_files

    decrypted_files = kms_client.decrypt_submission(
        key_id=xms_key.kms_key.key_id,
        submission_xml=submission_xml,
        enc_files=get_encrypted_files(),
    )

    # Replace encrypted submission with decrypted submission
    # Save history before replacement
    history = InstanceHistory(
        checksum=instance.checksum,
        xml=instance.xml,
        xform_instance=instance,
        uuid=instance.uuid,
        geom=instance.geom,
        submission_date=instance.last_edited or instance.date_created,
    )
    decrypted_attachment_ids = []

    for original_name, decrypted_file in decrypted_files:
        if original_name.lower() == "submission.xml":
            # Replace submission with decrypted submission
            xml = decrypted_file.getvalue()

            instance.xml = xml.decode("utf-8")
            instance.checksum = sha256(xml).hexdigest()
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


@transaction.atomic()
def disable_xform_encryption(xform, disabled_by=None):
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

    json_dict = xform.json_dict()
    json_dict["version"] = new_version
    del json_dict["public_key"]

    survey = create_survey_element_from_dict(json_dict)

    xform.json = survey.to_json_dict()
    xform.xml = survey.to_xml()
    xform.version = new_version
    xform.public_key = None
    xform.encrypted = False
    xform.save()

    # Create record of this version
    create_xform_version(xform=xform, user=disabled_by)
