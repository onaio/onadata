"""
Key management utility functions
"""

from datetime import datetime
from datetime import timezone as tz

from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from valigetta.kms import AWSKMSClient

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.logger.models import KMSKey
from onadata.apps.logger.models.xform import create_survey_element_from_dict
from onadata.libs.utils.model_tools import queryset_iterator


def create_key(org: OrganizationProfile) -> KMSKey:
    """Create KMS key.

    :param org: Organization that owns the key
    :return: KMSKey
    """
    client = AWSKMSClient(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_KMS_REGION_NAME,
    )
    now = datetime.now(tz=tz.utc)
    description = f"Key-{now.strftime('%Y-%m-%d')}"
    metadata = client.create_key(description=description)
    client.key_id = metadata["KeyId"]
    public_key = client.get_public_key().decode("utf-8")
    next_rotation_at = None

    if hasattr(settings.KMS_ROTATION_DURATION):
        next_rotation_at = now + settings.KMS_ROTATION_DURATION

    content_type = ContentType.objects.get_for_model(org)

    return KMSKey.objects.create(
        key_id=metadata["KeyId"],
        description=description,
        public_key=public_key,
        provider=KMSKey.KMSProvider.AWS,
        next_rotation_at=next_rotation_at,
        content_type=content_type,
        object_id=org.pk,
    )


def rotate_key(kms_key: KMSKey) -> KMSKey:
    """Rotate KMS key.

    :param kms_key: KMSKey
    :return: New KMSKey
    """
    # AWS KMS does not allow rotation of asymmetric keys,
    # so we create a new key
    new_key = create_key(kms_key.content_object)

    kms_key.rotated_at = datetime.now(tz=tz.utc)
    kms_key.save(update_fields=["rotated_at"])

    # Update forms using the old key to use the new key
    xform_qs = kms_key.xforms.all()

    for xform in queryset_iterator(xform_qs):
        new_version = datetime.now(tz=tz.utc).strftime("%Y%m%d%H%M")
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
    client = AWSKMSClient(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_KMS_REGION_NAME,
    )
    client.key_id = kms_key.key_id
    client.disable_key()
    kms_key.is_active = False
    kms_key.save()
