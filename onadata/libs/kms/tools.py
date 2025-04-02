"""
Key management utility functions
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.logger.models import KMSKey
from onadata.apps.logger.models.xform import create_survey_element_from_dict
from onadata.libs.kms.clients import AWSKMSClient
from onadata.libs.utils.model_tools import queryset_iterator

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
    Strips public key comments and spaces from a public key ``value``.
    """
    if value.startswith("-----BEGIN PUBLIC KEY-----") and value.endswith(
        "-----END PUBLIC KEY-----"
    ):
        return (
            value.replace("-----BEGIN PUBLIC KEY-----", "")
            .replace("-----END PUBLIC KEY-----", "")
            .replace(" ", "")
            .rstrip()
        )

    return value


def create_key(org: OrganizationProfile) -> KMSKey:
    """Create KMS key.

    :param org: Organization that owns the key
    :return: KMSKey
    """
    kms_client = get_kms_client()
    now = timezone.now()
    description = f"Key-{now.strftime('%Y-%m-%d')}"
    metadata = kms_client.create_key(description=description)
    next_rotation_at = None

    if hasattr(settings, "KMS_ROTATION_DURATION") and isinstance(
        settings.KMS_ROTATION_DURATION, timedelta
    ):
        next_rotation_at = now + settings.KMS_ROTATION_DURATION

    content_type = ContentType.objects.get_for_model(org)
    provider_choice_map = {
        "AWS": KMSKey.KMSProvider.AWS,
    }
    provider = provider_choice_map.get(_get_kms_provider().upper())

    return KMSKey.objects.create(
        key_id=metadata["key_id"],
        description=description,
        public_key=clean_public_key(metadata["public_key"]),
        provider=provider,
        next_rotation_at=next_rotation_at,
        content_type=content_type,
        object_id=org.pk,
    )


def rotate_key(kms_key: KMSKey) -> KMSKey:
    """Rotate KMS key.

    :param kms_key: KMSKey
    :return: New KMSKey
    """
    # Rotation of asymmetric keys is not allowed
    # so we create a new key
    new_key = create_key(kms_key.content_object)

    kms_key.rotated_at = timezone.now()
    kms_key.save(update_fields=["rotated_at"])

    # Update forms using the old key to use the new key
    xform_qs = kms_key.xforms.all()

    for xform in queryset_iterator(xform_qs):
        new_version = timezone.now().strftime("%Y%m%d%H%M")
        json_dict = xform.json_dict()
        json_dict["public_key"] = new_key.public_key
        json_dict["version"] = new_version
        survey = create_survey_element_from_dict(json_dict)
        xform.json = survey.to_json_dict()
        xform.xml = survey.to_xml()
        xform.version = new_version
        xform.public_key = new_key.public_key
        xform.save(update_fields=["json", "xml", "version", "xml", "public_key"])
        xform.kms_keys.create(version=new_version, kms_key=new_key)

    return new_key


def disable_key(kms_key: KMSKey) -> None:
    """Disable KMS key.

    :param kms_key: KMSKey
    """
    kms_client = get_kms_client()
    kms_client.disable_key(kms_key.key_id)
    kms_key.is_active = False
    kms_key.save()
