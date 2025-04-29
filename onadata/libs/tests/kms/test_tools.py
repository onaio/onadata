"""Tests for onadata.libs.kms.kms_tools"""

import base64
from datetime import datetime, timedelta
from datetime import timezone as tz
from hashlib import md5, sha256
from io import BytesIO
from unittest.mock import patch
from xml.etree.ElementTree import ParseError

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import File
from django.template.loader import render_to_string
from django.test import override_settings
from django.utils import timezone
from django.utils.html import strip_tags

import boto3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from moto import mock_aws
from valigetta.decryptor import _get_submission_iv
from valigetta.exceptions import InvalidSubmission

from onadata.apps.logger.models import Attachment, Instance, KMSKey, SurveyType
from onadata.apps.logger.models.xform import create_survey_element_from_dict
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.exceptions import EncryptionError
from onadata.libs.kms.clients import AWSKMSClient
from onadata.libs.kms.tools import (
    clean_public_key,
    create_key,
    decrypt_instance,
    disable_key,
    disable_xform_encryption,
    encrypt_xform,
    get_kms_client,
    is_instance_encrypted,
    rotate_key,
    send_key_rotation_notification,
)


class GetKMSClientTestCase(TestBase):
    """Tests for get_kms_client"""

    @override_settings(
        KMS_PROVIDER="AWS",
        AWS_ACCESS_KEY_ID="fake-id",
        AWS_SECRET_ACCESS_KEY="fake-secret",
        AWS_KMS_REGION_NAME="us-east-1",
    )
    def test_returns_client(self):
        """Configured client is returned."""
        client = get_kms_client()

        self.assertTrue(isinstance(client, AWSKMSClient))

    @override_settings(
        KMS_PROVIDER="foo",
        AWS_ACCESS_KEY_ID="fake-id",
        AWS_SECRET_ACCESS_KEY="fake-secret",
        AWS_KMS_REGION_NAME="us-east-1",
    )
    def test_invalid_provider(self):
        """Invalid provider is handled."""

        with self.assertRaises(ImproperlyConfigured) as exc_info:
            get_kms_client()

        self.assertEqual(str(exc_info.exception), "Unsupported KMS provider: foo")

    @override_settings(
        AWS_ACCESS_KEY_ID="fake-id",
        AWS_SECRET_ACCESS_KEY="fake-secret",
        AWS_KMS_REGION_NAME="us-east-1",
    )
    def test_default_client(self):
        """AWS is the default provider."""
        client = get_kms_client()

        self.assertTrue(isinstance(client, AWSKMSClient))


@mock_aws
@override_settings(
    KMS_PROVIDER="AWS",
    AWS_ACCESS_KEY_ID="fake-id",
    AWS_SECRET_ACCESS_KEY="fake-secret",
    AWS_KMS_REGION_NAME="us-east-1",
)
class CreateKeyTestCase(TestBase):
    """Tests for create_key"""

    def setUp(self):
        super().setUp()

        self.org = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        self.content_type = ContentType.objects.get_for_model(self.org)

    @patch("django.utils.timezone.now")
    def test_create_key(self, mock_now):
        """KMSKey is created."""
        mock_now.return_value = datetime(2025, 4, 2, tzinfo=tz.utc)
        kms_key = create_key(self.org, created_by=self.user)

        self.assertEqual(KMSKey.objects.count(), 1)
        self.assertEqual(kms_key.description, "Key-2025-04-02")
        self.assertEqual(kms_key.content_type, self.content_type)
        self.assertEqual(kms_key.object_id, self.org.pk)
        self.assertIsNotNone(kms_key.key_id)
        self.assertIsNotNone(kms_key.public_key)
        self.assertIsNone(kms_key.disabled_at)
        self.assertIsNone(kms_key.disabled_by)
        self.assertIsNone(kms_key.expiry_date)
        self.assertIsNone(kms_key.grace_end_date)
        self.assertEqual(kms_key.provider, KMSKey.KMSProvider.AWS)
        self.assertEqual(kms_key.created_by, self.user)
        # Public PEM-encoded key is saved without the header and footer
        self.assertNotIn("-----BEGIN PUBLIC KEY-----", kms_key.public_key)
        self.assertNotIn("-----END PUBLIC KEY-----", kms_key.public_key)

    @override_settings(KMS_ROTATION_DURATION=timedelta(days=365))
    @patch("django.utils.timezone.now")
    def test_expiry_date(self, mock_now):
        """Expiry date is set if rotation duration available."""
        mocked_now = datetime(2025, 4, 2, tzinfo=tz.utc)
        mock_now.return_value = mocked_now

        kms_key = create_key(self.org)

        self.assertEqual(kms_key.expiry_date, mocked_now + timedelta(days=365))

    @patch("django.utils.timezone.now")
    def test_duplicate_description(self, mock_now):
        """Duplicate description is appended a suffix."""
        mock_now.return_value = datetime(2025, 4, 2, tzinfo=tz.utc)

        # Simulate existing description for the same organization
        KMSKey.objects.create(
            key_id="fake-key-id",
            description="Key-2025-04-02",
            public_key="fake-pub-key",
            content_type=self.content_type,
            object_id=self.org.pk,
            provider=KMSKey.KMSProvider.AWS,
        )

        # Duplicate 1
        kms_key = create_key(self.org)

        self.assertEqual(kms_key.description, "Key-2025-04-02-v2")

        # Duplicate 2
        kms_key = create_key(self.org)

        self.assertEqual(kms_key.description, "Key-2025-04-02-v3")

    def test_created_by_optional(self):
        """created_by is optional."""
        kms_key = create_key(self.org)

        self.assertIsNone(kms_key.created_by)

    @patch("onadata.libs.kms.tools.logger.error")
    def test_invalid_rotation_duration(self, mock_logger):
        """Invalid rotation duration is handled."""
        with override_settings(KMS_ROTATION_DURATION="invalid"):
            create_key(self.org)

        # KMSKey is still created
        self.assertEqual(KMSKey.objects.count(), 1)
        kms_key = KMSKey.objects.first()

        self.assertIsNone(kms_key.expiry_date)
        self.assertIsNone(kms_key.grace_end_date)

        mock_logger.assert_called_once_with(
            "KMS_ROTATION_DURATION is set to an invalid value: %s",
            "invalid",
        )


@patch("onadata.libs.kms.tools.create_key")
class RotateKeyTestCase(TestBase):
    """Tests for rotate_key"""

    def setUp(self):
        super().setUp()

        self.org = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        self.content_type = ContentType.objects.get_for_model(self.org)
        self.mocked_now = datetime(2025, 4, 3, 12, 20, tzinfo=tz.utc)
        self.kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            description="Key-2025-04-03",
            public_key="fake-pub-key",
            content_type=self.content_type,
            object_id=self.org.pk,
            provider=KMSKey.KMSProvider.AWS,
            expiry_date=self.mocked_now - timedelta(hours=2),
        )
        self._publish_transportation_form()
        self.xform.kms_keys.create(
            kms_key=self.kms_key,
            version=self.xform.version,
        )
        self.mock_key_data = {
            "key_id": "new-key-id",
            "description": "Key-2025-04-03-v2",
            "public_key": "new-pub-key",
            "content_type": self.content_type,
            "object_id": self.org.pk,
            "provider": KMSKey.KMSProvider.AWS,
        }

    def create_mock_key(self):
        return KMSKey.objects.create(**self.mock_key_data)

    @patch("django.utils.timezone.now")
    def test_rotate(self, mock_now, mock_create_key):
        """KMS key is rotated."""
        mock_now.return_value = self.mocked_now
        mock_create_key.return_value = new_key = self.create_mock_key()

        rotate_key(
            kms_key=self.kms_key,
            rotated_by=self.user,
            rotation_reason="Test rotation",
        )

        self.xform.refresh_from_db()

        # New key is created since rotation of asymmetric is not allowed
        mock_create_key.assert_called_once_with(
            self.kms_key.content_object,
            created_by=self.user,
        )

        # Forms using old key are updated to use new key
        json_dict = self.xform.json_dict()
        survey = create_survey_element_from_dict(json_dict)
        self.assertEqual(json_dict.get("public_key"), new_key.public_key)
        self.assertEqual(json_dict.get("version"), "202504031220")
        self.assertEqual(self.xform.version, "202504031220")
        self.assertEqual(self.xform.public_key, new_key.public_key)
        self.assertTrue(self.xform.encrypted)
        self.assertEqual(self.xform.xml, survey.to_xml())
        self.assertTrue(
            self.xform.kms_keys.filter(
                kms_key=new_key, version="202504031220", encrypted_by=self.user
            ).exists()
        )
        # A XFormVersion of the new version is created
        self.assertTrue(self.xform.versions.filter(version="202504031220").exists())
        # Old key is marked as rotated
        self.kms_key.refresh_from_db()
        self.assertEqual(self.kms_key.rotated_at, self.mocked_now)
        self.assertEqual(self.kms_key.rotated_by, self.user)
        self.assertEqual(self.kms_key.rotation_reason, "Test rotation")

    @patch("django.utils.timezone.now")
    def test_rotated_by_optional(self, mock_now, mock_create_key):
        """rotated_by is optional"""
        mock_now.return_value = self.mocked_now
        mock_create_key.return_value = new_key = self.create_mock_key()

        rotate_key(self.kms_key)

        xform_key = self.xform.kms_keys.get(kms_key=new_key, version="202504031220")

        self.assertIsNone(xform_key.encrypted_by)

        mock_create_key.assert_called_once_with(
            self.kms_key.content_object, created_by=None
        )
        self.kms_key.refresh_from_db()

        self.assertIsNone(self.kms_key.rotated_by)

    def test_rotation_reason_optional(self, mock_create_key):
        """rotation_reason is optional"""
        mock_create_key.return_value = self.create_mock_key()

        rotate_key(self.kms_key)

        self.kms_key.refresh_from_db()

        self.assertIsNone(self.kms_key.rotation_reason)

    @patch("django.utils.timezone.now")
    def test_pre_mature_rotation(self, mock_now, mock_create_key):
        """Expiry date is set to the current date if it is in the future."""
        mock_now.return_value = self.mocked_now
        mock_create_key.return_value = self.create_mock_key()
        # Set the expiry date into the future
        self.kms_key.expiry_date = self.mocked_now + timedelta(days=30)
        self.kms_key.grace_end_date = self.kms_key.expiry_date + timedelta(days=60)
        self.kms_key.save()

        grace_period_duration = timedelta(days=30)

        with override_settings(KMS_GRACE_PERIOD_DURATION=grace_period_duration):
            rotate_key(self.kms_key)

        self.kms_key.refresh_from_db()

        self.assertEqual(self.kms_key.expiry_date, self.mocked_now)
        self.assertEqual(
            self.kms_key.grace_end_date, self.mocked_now + grace_period_duration
        )

    @patch("django.utils.timezone.now")
    @patch("onadata.libs.kms.tools.logger.error")
    def test_invalid_grace_period_duration(
        self, mock_logger, mock_now, mock_create_key
    ):
        """Default grace period duration is used if duration is invalid."""
        mock_now.return_value = self.mocked_now
        mock_create_key.return_value = self.create_mock_key()

        with override_settings(KMS_GRACE_PERIOD_DURATION="invalid"):
            rotate_key(self.kms_key)

        mock_logger.assert_called_once_with(
            "KMS_GRACE_PERIOD_DURATION is set to an invalid value: %s",
            "invalid",
        )

        self.kms_key.refresh_from_db()

        # Default grace period duration is 30 days
        self.assertEqual(
            self.kms_key.grace_end_date,
            self.kms_key.expiry_date + timedelta(days=30),
        )

    def test_grace_duration_missing(self, mock_create_key):
        """Default grace duration is used if duration is missing."""
        mock_create_key.return_value = self.create_mock_key()

        with override_settings(KMS_GRACE_PERIOD_DURATION=None):
            rotate_key(self.kms_key)

        self.kms_key.refresh_from_db()

        self.assertEqual(
            self.kms_key.grace_end_date,
            self.kms_key.expiry_date + timedelta(days=30),
        )

    @patch("onadata.libs.kms.tools.importlib.import_module")
    def test_xform_list_cache_invalidated(self, mock_import_module, mock_create_key):
        """FormList endpoint cache is invalidated."""
        mock_create_key.return_value = self.create_mock_key()
        mock_api_tools = mock_import_module.return_value
        mock_api_tools.invalidate_xform_list_cache.return_value = None

        rotate_key(self.kms_key)

        mock_api_tools.invalidate_xform_list_cache.assert_called_once_with(self.xform)

    def test_disabled_key(self, mock_create_key):
        """Rotating an already disabled key is not allowed."""
        mock_create_key.return_value = self.create_mock_key()

        self.kms_key.disabled_at = timezone.now()
        self.kms_key.save()

        with self.assertRaises(EncryptionError) as exc_info:
            rotate_key(kms_key=self.kms_key, rotated_by=self.user)

        mock_create_key.assert_not_called()

        self.assertEqual(str(exc_info.exception), "Key is disabled.")

    def test_already_rotated_key(self, mock_create_key):
        """Rotating an already rotated key is not allowed."""
        mock_create_key.return_value = self.create_mock_key()

        self.kms_key.rotated_at = timezone.now()
        self.kms_key.save()

        with self.assertRaises(EncryptionError) as exc_info:
            rotate_key(self.kms_key, rotated_by=self.user)

        mock_create_key.assert_not_called()

        self.assertEqual(str(exc_info.exception), "Key already rotated.")


@mock_aws
@override_settings(
    KMS_PROVIDER="AWS",
    AWS_ACCESS_KEY_ID="fake-id",
    AWS_SECRET_ACCESS_KEY="fake-secret",
    AWS_KMS_REGION_NAME="us-east-1",
)
@patch.object(AWSKMSClient, "disable_key")
class DisableKeyTestCase(TestBase):
    """Tests for disable_key."""

    def setUp(self):
        super().setUp()

        self.org = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        self.content_type = ContentType.objects.get_for_model(self.org)
        self.kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            description="Key-2025-04-03",
            public_key="fake-pub-key",
            content_type=self.content_type,
            object_id=self.org.pk,
            provider=KMSKey.KMSProvider.AWS,
        )

    @patch("django.utils.timezone.now")
    def test_disable(self, mock_now, mock_aws_disable):
        """KMSKey is disabled."""
        mocked_now = datetime(2025, 4, 3, 12, 20, tzinfo=tz.utc)
        mock_now.return_value = mocked_now

        disable_key(kms_key=self.kms_key, disabled_by=self.user)

        mock_aws_disable.assert_called_once_with("fake-key-id")

        self.kms_key.refresh_from_db()

        self.assertEqual(self.kms_key.disabled_at, mocked_now)
        self.assertEqual(self.kms_key.disabled_by, self.user)

    def test_disabled_by_optional(self, mock_aws_disable):
        """disabled_by is optional."""
        disable_key(self.kms_key)

        self.kms_key.refresh_from_db()

        self.assertIsNotNone(self.kms_key.disabled_at)
        self.assertIsNone(self.kms_key.disabled_by)


class EncryptXFormTestCase(TestBase):
    """Test encrypt_xform works."""

    def setUp(self):
        super().setUp()

        self.org = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        self.content_type = ContentType.objects.get_for_model(self.org)
        self.kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            description="Key-2025-04-03",
            public_key="fake-pub-key",
            content_type=self.content_type,
            object_id=self.org.pk,
            provider=KMSKey.KMSProvider.AWS,
        )
        self._publish_transportation_form()
        # Transfer xform to organization
        self.xform.user = self.org.user
        self.xform.save()

    @patch("django.utils.timezone.now")
    def test_encrypt_xform(self, mock_now):
        """Unencrypted XForm is encrypted."""
        mocked_now = datetime(2025, 4, 10, 12, 27, tzinfo=tz.utc)
        mock_now.return_value = mocked_now

        self.assertFalse(self.xform.encrypted)
        old_hash = self.xform.hash

        encrypt_xform(xform=self.xform, encrypted_by=self.user)

        self.xform.refresh_from_db()
        json_dict = self.xform.json_dict()
        survey = create_survey_element_from_dict(json_dict)

        self.assertEqual(json_dict.get("public_key"), "fake-pub-key")
        self.assertEqual(json_dict.get("version"), "202504101227")

        self.assertTrue(self.xform.encrypted)
        self.assertEqual(self.xform.xml, survey.to_xml())
        self.assertEqual(self.xform.public_key, self.kms_key.public_key)
        self.assertTrue(self.xform.encrypted)
        self.assertEqual(self.xform.version, "202504101227")
        self.assertTrue(self.xform.is_kms_encrypted)
        # Hash should be updated
        self.assertNotEqual(self.xform.hash, old_hash)

        xform_kms_key_qs = self.xform.kms_keys.filter(
            kms_key=self.kms_key, version=self.xform.version, encrypted_by=self.user
        )

        self.assertTrue(xform_kms_key_qs.exists())
        # A XFormVersion of the new version is created
        self.assertTrue(self.xform.versions.filter(version="202504101227").exists())

    def test_kms_key_not_found(self):
        """No KMSKey found for an organization."""
        self.kms_key.delete()

        with self.assertRaises(EncryptionError) as exc_info:
            encrypt_xform(xform=self.xform, encrypted_by=self.user)

        self.assertEqual(
            str(exc_info.exception), "No encryption key found for the organization."
        )

        # KMSKey exists but disabled
        self.kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            description="Key-2025-04-03",
            public_key="fake-pub-key",
            content_type=self.content_type,
            object_id=self.org.pk,
            provider=KMSKey.KMSProvider.AWS,
            disabled_at=timezone.now(),
        )

        with self.assertRaises(EncryptionError) as exc_info:
            encrypt_xform(xform=self.xform, encrypted_by=self.user)

        self.assertEqual(
            str(exc_info.exception), "No encryption key found for the organization."
        )

    def test_owner_is_org(self):
        """XForm owner must be an organization user."""
        self.xform.user = self.user
        self.xform.save()

        with self.assertRaises(EncryptionError) as exc_info:
            encrypt_xform(xform=self.xform, encrypted_by=self.user)

        self.assertEqual(
            str(exc_info.exception), "XForm owner is not an organization user."
        )

    def test_encrypted_by_optional(self):
        """encrypted_by is optional."""
        encrypt_xform(self.xform)

        xform_key = self.xform.kms_keys.get(
            kms_key=self.kms_key, version=self.xform.version
        )

        self.assertIsNone(xform_key.encrypted_by)

    def test_should_have_zero_submissions(self):
        """XForm should have zero submissions."""
        self.xform.num_of_submissions = 90
        self.xform.save()

        with self.assertRaises(EncryptionError) as exc_info:
            encrypt_xform(xform=self.xform, encrypted_by=self.user)

        self.assertEqual(str(exc_info.exception), "XForm already has submissions.")

    @patch("onadata.libs.kms.tools.importlib.import_module")
    def test_xform_list_cache_invalidated(self, mock_import_module):
        """FormList endpoint cache is invalidated."""
        mock_api_tools = mock_import_module.return_value
        mock_api_tools.invalidate_xform_list_cache.return_value = None

        encrypt_xform(self.xform, encrypted_by=self.user)

        mock_api_tools.invalidate_xform_list_cache.assert_called_once_with(self.xform)


@mock_aws
@override_settings(
    KMS_PROVIDER="AWS",
    AWS_ACCESS_KEY_ID="fake-id",
    AWS_SECRET_ACCESS_KEY="fake-secret",
    AWS_KMS_REGION_NAME="us-east-1",
)
class DecryptInstanceTestCase(TestBase):
    """Tests for decrypt_instance."""

    def setUp(self):
        super().setUp()
        self.instance_version = "202502131337"
        self.instance_uuid = "uuid:a10ead67-7415-47da-b823-0947ab8a8ef0"
        self.form_id = "test_valigetta"

        self.org = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        self.dec_submission_xml = f"""
        <data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx="http://openrosa.org/xforms"
            id="{self.form_id}" version="{self.instance_version}">
            <formhub>
                <uuid>76972fb82e41400c840019938b188ce8</uuid>
            </formhub>
            <sunset>sunset.png</sunset>
            <forest>forest.mp4</forest>
            <meta>
                <instanceID>{self.instance_uuid}</instanceID>
            </meta>
        </data>
        """.strip()
        self.dec_submission_file = BytesIO(self.dec_submission_xml.encode("utf-8"))
        self.dec_media = {
            "sunset.png": BytesIO(b"Fake PNG image data"),
            "forest.mp4": BytesIO(b"Fake MP4 video data"),
        }
        dec_aes_key = b"0123456789abcdef0123456789abcdef"
        kms_key = create_key(self.org)
        enc_aes_key = self._encrypt(key_id=kms_key.key_id, plain_text=dec_aes_key)
        enc_signature = self._get_encrypted_signature(
            key_id=kms_key.key_id,
            enc_aes_key=enc_aes_key,
            dec_media=self.dec_media,
            dec_submission=self.dec_submission_file,
        )
        enc_key_b64 = base64.b64encode(enc_aes_key).decode("utf-8")
        enc_signature_b64 = base64.b64encode(enc_signature).decode("utf-8")

        self.metadata_xml = f"""
        <data xmlns="http://opendatakit.org/submissions" encrypted="yes"
            id="{self.form_id}" version="{self.instance_version}">
            <base64EncryptedKey>{enc_key_b64}</base64EncryptedKey>
            <meta xmlns="http://openrosa.org/xforms">
                <instanceID>{self.instance_uuid}</instanceID>
            </meta>
            <media>
                <file>sunset.png.enc</file>
                <file>forest.mp4.enc</file>
            </media>
            <encryptedXmlFile>submission.xml.enc</encryptedXmlFile>
            <base64EncryptedElementSignature>{enc_signature_b64}</base64EncryptedElementSignature>
        </data>
        """.strip()
        self.metadata_xml_file = BytesIO(self.metadata_xml.encode("utf-8"))

        md = """
        | survey  |
        |         | type  | name   | label                |
        |         | photo | sunset | Take photo of sunset |
        |         | video | forest | Take a video of forest|
        """
        self.xform = self._publish_markdown(md, self.user, id_string="nature")
        survey_type = SurveyType.objects.create(slug="slug-foo")
        self.instance = Instance.objects.create(
            xform=self.xform,
            xml=self.metadata_xml,
            user=self.user,
            survey_type=survey_type,
            checksum=sha256(self.metadata_xml_file.getvalue()).hexdigest(),
        )
        self.instance.refresh_from_db()
        dec_files = [
            ("sunset.png", self.dec_media["sunset.png"]),
            ("forest.mp4", self.dec_media["forest.mp4"]),
            ("submission.xml", self.dec_submission_file),
        ]
        attachments = []

        for index, (name, file) in enumerate(dec_files, start=1):
            enc_file_name = f"{name}.enc"
            enc_file = self._encrypt_file(dec_aes_key, index, file.getvalue())
            attachment = Attachment(
                instance=self.instance,
                xform=self.xform,
                media_file=File(enc_file, name=enc_file_name),
                mimetype="application/octet-stream",
                extension="enc",
                file_size=len(file.getbuffer()),
                name=enc_file_name,
            )
            attachments.append(attachment)

        Attachment.objects.bulk_create(attachments)

        self.xform.kms_keys.create(version="202502131337", kms_key=kms_key)

    def _encrypt(self, key_id, plain_text):
        boto3_kms_client = boto3.client("kms", region_name="us-east-1")

        response = boto3_kms_client.encrypt(KeyId=key_id, Plaintext=plain_text)
        return response["CiphertextBlob"]

    def _get_encrypted_signature(self, key_id, enc_aes_key, dec_submission, dec_media):
        def compute_file_md5(file):
            file.seek(0)
            return md5(file.read()).hexdigest().zfill(32)

        signature_parts = [
            self.form_id,
            self.instance_version,
            base64.b64encode(enc_aes_key).decode("utf-8"),
            self.instance_uuid,
        ]
        # Add media files
        for media_name, media_file in dec_media.items():
            file_md5_hash = compute_file_md5(media_file)
            signature_parts.append(f"{media_name}::{file_md5_hash}")

        # Add submission file
        file_md5_hash = compute_file_md5(dec_submission)
        signature_parts.append(f"submission.xml::{file_md5_hash}")
        # Construct final signature string
        signature_data = "\n".join(signature_parts) + "\n"
        # Compute MD5 digest before encrypting
        signature_md5_digest = md5(signature_data.encode("utf-8")).digest()
        # Encrypt MD5 digest
        return self._encrypt(key_id=key_id, plain_text=signature_md5_digest)

    def _encrypt_file(self, dec_aes_key, iv_counter, data):
        iv = _get_submission_iv(self.instance_uuid, dec_aes_key, iv_counter=iv_counter)
        cipher_aes = AES.new(dec_aes_key, AES.MODE_CFB, iv=iv, segment_size=128)
        padded_data = pad(data, AES.block_size)

        return BytesIO(cipher_aes.encrypt(padded_data))

    def _compute_file_sha256(self, buffer):
        return sha256(buffer.getvalue()).hexdigest()

    def test_decrypt_submission(self):
        """Decrypt submission is successful."""
        self.assertTrue(self.instance.is_encrypted)

        decrypt_instance(self.instance)

        self.instance.refresh_from_db()

        # Submission replaced
        self.assertEqual(self.instance.xml, self.dec_submission_xml)
        self.assertEqual(
            self.instance.checksum,
            sha256(self.dec_submission_file.getvalue()).hexdigest(),
        )
        self.assertFalse(self.instance.is_encrypted)

        # Decrypted media files are saved
        att_qs = Attachment.objects.filter(
            xform=self.xform, instance=self.instance
        ).order_by("pk")

        self.assertEqual(att_qs.count(), 5)
        self.assertEqual(att_qs[3].name, "sunset.png")
        self.assertEqual(att_qs[3].extension, "png")
        self.assertEqual(att_qs[3].mimetype, "image/png")

        with att_qs[3].media_file.open("rb") as dec_file:
            buffer = BytesIO(dec_file.read())
            original_file = self.dec_media["sunset.png"]

            self.assertEqual(
                self._compute_file_sha256(buffer),
                self._compute_file_sha256(original_file),
            )
            self.assertEqual(att_qs[3].file_size, len(original_file.getbuffer()))

        self.assertEqual(att_qs[4].name, "forest.mp4")
        self.assertEqual(att_qs[4].extension, "mp4")
        self.assertEqual(att_qs[4].mimetype, "video/mp4")

        with att_qs[4].media_file.open("rb") as dec_file:
            buffer = BytesIO(dec_file.read())
            original_file = self.dec_media["forest.mp4"]

            self.assertEqual(
                self._compute_file_sha256(buffer),
                self._compute_file_sha256(original_file),
            )
            self.assertEqual(att_qs[4].file_size, len(original_file.getbuffer()))

        # Encrypted media files are soft deleted
        self.assertEqual(att_qs.filter(deleted_at__isnull=False).count(), 3)
        self.assertIsNotNone(att_qs[0].deleted_at)
        self.assertIsNotNone(att_qs[1].deleted_at)
        self.assertIsNotNone(att_qs[2].deleted_at)
        # Old submission is stored in history
        history_qs = self.instance.submission_history.all()

        self.assertEqual(history_qs.count(), 1)

        history = history_qs.first()

        self.assertEqual(history.xml, self.metadata_xml)
        self.assertEqual(
            history.checksum, sha256(self.metadata_xml_file.getvalue()).hexdigest()
        )

    def test_unencrypted_submission(self):
        """Unencrypted Instance is rejected."""
        self._publish_transportation_form_and_submit_instance()
        instance = Instance.objects.order_by("-date_created").first()
        old_xml = instance.xml
        old_date_modified = instance.date_modified

        with self.assertRaises(InvalidSubmission) as exc_info:
            decrypt_instance(instance)

        self.assertEqual(str(exc_info.exception), "Instance is not encrypted.")

        instance.refresh_from_db()

        # No update was made to Instance
        self.assertEqual(instance.xml, old_xml)
        self.assertEqual(instance.date_modified, old_date_modified)


class DisableXFormEncryptionTestCase(TestBase):
    """Tetss for `disable_xform_encryption`"""

    def setUp(self):
        super().setUp()

        self.org = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        self.content_type = ContentType.objects.get_for_model(self.org)
        self.kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            description="Key-2025-04-03",
            public_key="fake-pub-key",
            content_type=self.content_type,
            object_id=self.org.pk,
            provider=KMSKey.KMSProvider.AWS,
        )
        self._publish_transportation_form()
        # Transfer xform to organization
        self.xform.user = self.org.user
        self.xform.save()

    def test_encryption_disabled(self):
        """Disabling XForm encryption works"""
        # Encrypt XForm
        self._encrypt_xform(self.xform, self.kms_key)

        old_hash = self.xform.hash

        with patch("django.utils.timezone.now") as mock_now:
            mocked_now = datetime(2025, 4, 10, 10, 38, tzinfo=tz.utc)
            mock_now.return_value = mocked_now

            disable_xform_encryption(self.xform, disabled_by=self.user)

        self.xform.refresh_from_db()
        json_dict = self.xform.json_dict()
        survey = create_survey_element_from_dict(json_dict)

        self.assertIsNone(json_dict.get("public_key"))
        self.assertEqual(json_dict.get("version"), "202504101038")
        self.assertFalse(self.xform.encrypted)
        self.assertIsNone(self.xform.public_key)
        self.assertEqual(self.xform.version, "202504101038")
        self.assertEqual(self.xform.xml, survey.to_xml())
        self.assertNotEqual(self.xform.hash, old_hash)

        # New version is recorded
        xform_version_qs = self.xform.versions.filter(version="202504101038")

        self.assertTrue(xform_version_qs.exists())

        version = xform_version_qs.first()

        self.assertEqual(version.xml, self.xform.xml)
        self.assertEqual(version.created_by, self.user)

    def test_should_have_zero_submissions(self):
        """XForm should have zero submissions."""
        # Encrypt XForm
        self._encrypt_xform(self.xform, self.kms_key)

        self.xform.num_of_submissions = 90
        self.xform.save()

        with self.assertRaises(EncryptionError) as exc_info:
            disable_xform_encryption(self.xform, disabled_by=self.user)

        self.assertEqual(str(exc_info.exception), "XForm already has submissions.")

    def test_should_be_encrypted(self):
        """Unencrypted XForm is ignored."""
        old_version = self.xform.version
        disable_xform_encryption(self.xform, disabled_by=self.user)

        self.xform.refresh_from_db()

        self.assertEqual(self.xform.version, old_version)

    def test_non_kms_encryption(self):
        """XForm not encrypted via managed keys rejected."""
        self.xform.public_key = "fake-public-key"
        self.xform.save()

        with self.assertRaises(EncryptionError) as exc_info:
            disable_xform_encryption(self.xform, disabled_by=self.user)

        self.assertEqual(
            str(exc_info.exception), "XForm encryption is not via managed keys."
        )

    def test_disabled_by_optional(self):
        """disabled_by is optional."""
        # Encrypt XForm
        self._encrypt_xform(self.xform, self.kms_key)

        with patch("django.utils.timezone.now") as mock_now:
            mocked_now = datetime(2025, 4, 10, 10, 38, tzinfo=tz.utc)
            mock_now.return_value = mocked_now

            disable_xform_encryption(self.xform)

        xform_version_qs = self.xform.versions.filter(version="202504101038")

        self.assertTrue(xform_version_qs.exists())

        version = xform_version_qs.first()

        self.assertIsNone(version.created_by)

    @patch("onadata.libs.kms.tools.importlib.import_module")
    def test_xform_list_cache_invalidated(self, mock_import_module):
        """FormList endpoint cache is invalidated."""
        mock_api_tools = mock_import_module.return_value
        mock_api_tools.invalidate_xform_list_cache.return_value = None

        # Encrypt XForm
        self._encrypt_xform(self.xform, self.kms_key)

        disable_xform_encryption(self.xform)

        mock_api_tools.invalidate_xform_list_cache.assert_called_once_with(self.xform)


class CleanPublicKeyTestCase(TestBase):
    """Tests for `clean_public_key`"""

    def setUp(self):
        super().setUp()

        self.public_key = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxNlbF920Dj7CYsKYrxcK
PL0PatubLO2OhcMCpHgdbpGZscbWVAcXNkdjhmPhTuVPXmOa2Wjwe4ZkRfXJW2Iv
lvPm//UIWXhXUsNQaB9P
X4yxLWC0fZQ9T3ito8PcZ1nS+B39HYMkRSn9K5r65zRi
SZhwvTkhcwq7Cea+wX3UT/pfEx62Z8GZ3E8iiYrIcNv2DM+x+0yYmQEboXq1tlKE
twkF965z9mUTyXYfinrrHVx7xXhz1jbiWyOvTpiY8aAC35EaV3h/MdNXKk7WznJi
xdM
nhMo+jI88L3qfm4/rtWKuQ9/a268phlNj34uQeoDDHuRViQo00L5meE/pFptm
7QIDAQAB
-----END PUBLIC KEY-----"""

        self.clean_key = """
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxNlbF920Dj7CYsKYrxcK
PL0PatubLO2OhcMCpHgdbpGZscbWVAcXNkdjhmPhTuVPXmOa2Wjwe4ZkRfXJW2Iv
lvPm//UIWXhXUsNQaB9P
X4yxLWC0fZQ9T3ito8PcZ1nS+B39HYMkRSn9K5r65zRi
SZhwvTkhcwq7Cea+wX3UT/pfEx62Z8GZ3E8iiYrIcNv2DM+x+0yYmQEboXq1tlKE
twkF965z9mUTyXYfinrrHVx7xXhz1jbiWyOvTpiY8aAC35EaV3h/MdNXKk7WznJi
xdM
nhMo+jI88L3qfm4/rtWKuQ9/a268phlNj34uQeoDDHuRViQo00L5meE/pFptm
7QIDAQAB"""

    def test_public_key_with_headers(self):
        """Clean public key with headers and footers works"""
        cleaned_key = clean_public_key(self.public_key)

        self.assertEqual(cleaned_key, self.clean_key.strip())

    def test_public_key_without_headers(self):
        """Clean public key without headers and footers works"""
        cleaned_key = clean_public_key(self.clean_key)

        self.assertEqual(cleaned_key, self.clean_key.strip())


class IsInstanceEncryptedTestCase(TestBase):
    """Tests for `is_instance_encrypted`"""

    def test_encrypted_instance(self):
        """Returns True if Instance is encrypted."""
        manifest_xml = """
        <data xmlns="http://opendatakit.org/submissions" encrypted="yes"
            id="test_valigetta" version="202502131337">
            <base64EncryptedKey>fake0key</base64EncryptedKey>
            <meta xmlns="http://openrosa.org/xforms">
                <instanceID>uuid:a10ead67-7415-47da-b823-0947ab8a8ef0</instanceID>
            </meta>
            <media>
                <file>sunset.png.enc</file>
                <file>forest.mp4.enc</file>
            </media>
            <encryptedXmlFile>submission.xml.enc</encryptedXmlFile>
            <base64EncryptedElementSignature>fake-signature</base64EncryptedElementSignature>
        </data>
        """.strip()
        md = """
        | survey  |
        |         | type  | name   | label                |
        |         | photo | sunset | Take photo of sunset |
        |         | video | forest | Take a video of forest|
        """
        xform = self._publish_markdown(md, self.user, id_string="nature")
        survey_type = SurveyType.objects.create(slug="slug-foo")
        instance = Instance.objects.create(
            xform=xform,
            xml=manifest_xml,
            user=self.user,
            survey_type=survey_type,
        )
        self.assertTrue(is_instance_encrypted(instance))

    def test_unencrypted_instance(self):
        """Returns False if Instance unencrypted."""
        self._publish_transportation_form_and_submit_instance()
        instance = Instance.objects.order_by("-pk").first()

        self.assertFalse(is_instance_encrypted(instance))

    def test_invalid_xml(self):
        """Returns False if XML invalid."""
        self._publish_transportation_form_and_submit_instance()
        instance = Instance.objects.order_by("-pk").first()

        # Mock ElementTree.fromstring to throw ParseError
        with patch("xml.etree.ElementTree.fromstring", side_effect=ParseError):
            self.assertFalse(is_instance_encrypted(instance))


@override_settings(
    KMS_GRACE_PERIOD_DURATION=timedelta(days=30),
    DEFAULT_FROM_EMAIL="test@example.com",
)
@patch("onadata.libs.kms.tools.send_mass_mail")
class SendKeyRotationNotificationTestCase(TestBase):
    """Tests for `send_key_rotation_notification`"""

    def setUp(self):
        super().setUp()

        self.org = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        self.user.email = "bob@example.com"
        self.user.save()
        self.content_type = ContentType.objects.get_for_model(self.org)
        self.kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            description="Key-2025-04-29",
            public_key="fake-pub-key",
            content_type=self.content_type,
            object_id=self.org.pk,
            provider=KMSKey.KMSProvider.AWS,
            expiry_date=timezone.now() + timedelta(weeks=2),
        )
        self.friendly_date = lambda date: f'{date.strftime("%d %b, %Y %I:%M %p")} UTC'
        self.html_message = render_to_string(
            "organization/key_rotation_notification.html",
            {
                "organization_name": self.org.name,
                "rotation_date": self.friendly_date(self.kms_key.expiry_date),
                "grace_end_date": self.friendly_date(
                    self.kms_key.expiry_date + timedelta(days=30)
                ),
                "deployment_name": "Ona",
            },
        )

    @override_settings(KMS_ROTATION_NOTIFICATION_DURATION=timedelta(weeks=2))
    @patch("onadata.libs.kms.tools.get_organization_owners")
    def test_send_key_rotation_notification(
        self, mock_get_organization_owners, mock_send_mass_mail
    ):
        """Send key rotation notification works"""
        alice = self._create_user("alice", "alice", False)
        alice.email = "alice@example.com"
        alice.save()

        mock_get_organization_owners.return_value = [self.user, alice]

        send_key_rotation_notification()

        mass_mail_data = (
            (
                "Key Rotation for Organization: Valigetta Inc",
                strip_tags(self.html_message),
                self.html_message,
                "test@example.com",
                ["bob@example.com", "alice@example.com"],
            ),
        )

        mock_send_mass_mail.assert_called_once_with(mass_mail_data)

    @patch("onadata.libs.kms.tools.get_organization_owners")
    def test_no_organization_owners(
        self, mock_get_organization_owners, mock_send_mass_mail
    ):
        """Notification is not sent if no organization owners found."""
        mock_get_organization_owners.return_value = []

        send_key_rotation_notification()

        mock_send_mass_mail.assert_not_called()

    def test_no_keys_to_notify(self, mock_send_mass_mail):
        """Notification is not sent if no keys to notify."""
        self.kms_key.expiry_date = timezone.now() - timedelta(days=1)
        self.kms_key.save()

        send_key_rotation_notification()
        mock_send_mass_mail.assert_not_called()

    def test_default_notification_duration(self, mock_send_mass_mail):
        """Default notification duration is 2 weeks."""
        send_key_rotation_notification()

        mock_send_mass_mail.assert_called_once()

    def test_custom_deployment_name(self, mock_send_mass_mail):
        """Custom deployment name is used."""
        with override_settings(DEPLOYMENT_NAME="ToolBox"):
            send_key_rotation_notification()

        html_message = render_to_string(
            "organization/key_rotation_notification.html",
            {
                "organization_name": self.org.name,
                "rotation_date": self.friendly_date(self.kms_key.expiry_date),
                "grace_end_date": self.friendly_date(
                    self.kms_key.expiry_date + timedelta(days=30)
                ),
                "deployment_name": "ToolBox",
            },
        )
        mass_mail_data = (
            (
                "Key Rotation for Organization: Valigetta Inc",
                strip_tags(html_message),
                html_message,
                "test@example.com",
                ["bob@example.com"],
            ),
        )
        mock_send_mass_mail.assert_called_once_with(mass_mail_data)
