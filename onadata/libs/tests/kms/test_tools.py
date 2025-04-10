"""Tests for onadata.libs.kms.kms_tools"""

import base64
from datetime import datetime, timedelta
from datetime import timezone as tz
from hashlib import md5, sha256
from io import BytesIO
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import File
from django.test import override_settings
from django.utils import timezone

import boto3
from Crypto.Cipher import AES
from moto import mock_aws
from valigetta.decryptor import _get_submission_iv

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
    rotate_key,
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
        kms_key = create_key(self.org)

        self.assertEqual(KMSKey.objects.count(), 1)
        self.assertEqual(kms_key.description, "Key-2025-04-02")
        self.assertEqual(kms_key.content_type, self.content_type)
        self.assertEqual(kms_key.object_id, self.org.pk)
        self.assertIsNotNone(kms_key.key_id)
        self.assertIsNotNone(kms_key.public_key)
        self.assertIsNone(kms_key.disabled_at)
        self.assertIsNone(kms_key.disabled_by)
        self.assertIsNone(kms_key.expiry_date)
        self.assertEqual(kms_key.provider, KMSKey.KMSProvider.AWS)
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


@mock_aws
@override_settings(
    KMS_PROVIDER="AWS",
    AWS_ACCESS_KEY_ID="fake-id",
    AWS_SECRET_ACCESS_KEY="fake-secret",
    AWS_KMS_REGION_NAME="us-east-1",
)
class RotateKeyTestCase(TestBase):
    """Tests for rotate_key"""

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
        self.xform.kms_keys.create(
            kms_key=self.kms_key,
            version=self.xform.version,
        )

    @patch("django.utils.timezone.now")
    def test_rotate(self, mock_now):
        """KMS key is rotated."""
        mocked_now = datetime(2025, 4, 3, 12, 20, tzinfo=tz.utc)
        mock_now.return_value = mocked_now

        new_key = rotate_key(kms_key=self.kms_key, rotated_by=self.user)

        self.kms_key.refresh_from_db()
        self.xform.refresh_from_db()

        # New key is created since rotation of asymmetric is not
        # allowed
        self.assertEqual(KMSKey.objects.all().count(), 2)
        self.assertEqual(new_key.description, "Key-2025-04-03-v2")
        self.assertEqual(new_key.content_type, self.content_type)
        self.assertEqual(new_key.object_id, self.org.pk)
        self.assertIsNotNone(new_key.key_id)
        self.assertIsNotNone(new_key.public_key)
        self.assertEqual(new_key.provider, KMSKey.KMSProvider.AWS)
        self.assertNotIn("-----BEGIN PUBLIC KEY-----", new_key.public_key)
        self.assertNotIn("-----END PUBLIC KEY-----", new_key.public_key)

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

    @patch("django.utils.timezone.now")
    def test_rotated_by_optional(self, mock_now):
        """rotated_by is optional"""
        mocked_now = datetime(2025, 4, 3, 12, 20, tzinfo=tz.utc)
        mock_now.return_value = mocked_now

        new_key = rotate_key(self.kms_key)

        xform_key = self.xform.kms_keys.get(kms_key=new_key, version="202504031220")

        self.assertIsNone(xform_key.encrypted_by)


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

        xform_kms_key_qs = self.xform.kms_keys.filter(
            kms_key=self.kms_key, version=self.xform.version, encrypted_by=self.user
        )

        self.assertTrue(xform_kms_key_qs.exists())

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
        dec_files = [
            ("submission.xml", self.dec_submission_file),
            ("sunset.png", self.dec_media["sunset.png"]),
            ("forest.mp4", self.dec_media["forest.mp4"]),
        ]
        attachments = []

        for index, (name, file) in enumerate(dec_files):
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

    def _encrypt_file(self, dec_aes_key, index, data):
        iv = _get_submission_iv(self.instance_uuid, dec_aes_key, index=index)
        cipher_aes = AES.new(dec_aes_key, AES.MODE_CFB, iv=iv, segment_size=128)

        return BytesIO(cipher_aes.encrypt(data))

    def _compute_file_sha256(self, buffer):
        return sha256(buffer.getvalue()).hexdigest()

    def test_decrypt_submission(self):
        """Decrypt submission is successful."""
        decrypt_instance(self.instance)

        self.instance.refresh_from_db()

        # Submission replaced
        self.assertEqual(self.instance.xml, self.dec_submission_xml)
        self.assertEqual(
            self.instance.checksum,
            sha256(self.dec_submission_file.getvalue()).hexdigest(),
        )

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
        """No changes made to unencrypted submission."""
        self._publish_transportation_form_and_submit_instance()
        instance = Instance.objects.order_by("-date_created").first()
        old_xml = instance.xml
        old_date_modified = instance.date_modified

        decrypt_instance(instance)

        instance.refresh_from_db()

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
        self._encrypt_xform(self.xform)

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

        # New version is recorded
        xform_version_qs = self.xform.versions.filter(version="202504101038")

        self.assertTrue(xform_version_qs.exists())

        version = xform_version_qs.first()

        self.assertEqual(version.xml, self.xform.xml)
        self.assertEqual(version.created_by, self.user)

    def test_should_have_zero_submissions(self):
        """XForm should have zero submissions."""
        # Encrypt XForm
        self._encrypt_xform(self.xform)

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
        self._encrypt_xform(self.xform)

        with patch("django.utils.timezone.now") as mock_now:
            mocked_now = datetime(2025, 4, 10, 10, 38, tzinfo=tz.utc)
            mock_now.return_value = mocked_now

            disable_xform_encryption(self.xform)

        xform_version_qs = self.xform.versions.filter(version="202504101038")

        self.assertTrue(xform_version_qs.exists())

        version = xform_version_qs.first()

        self.assertIsNone(version.created_by)


class CleanPublicKeyTestCase(TestBase):
    """Tests for `clean_public_key`"""

    def test_ublic_key_with_headers(self):
        """Clean public key with headers and footers works"""
        public_key = """-----BEGIN PUBLIC KEY-----
        fake-public-key
        -----END PUBLIC KEY-----"""
        cleaned_key = clean_public_key(public_key)
        self.assertEqual(cleaned_key, "fake-public-key")

    def test_public_key_without_headers(self):
        """Clean public key without headers and footers works"""
        public_key = "fake-public-key"
        cleaned_key = clean_public_key(public_key)
        self.assertEqual(cleaned_key, "fake-public-key")

    def test_public_key_with_extra_whitespace(self):
        """Clean public key with extra whitespace works"""
        public_key = """-----BEGIN PUBLIC KEY-----

        fake-public-key

        -----END PUBLIC KEY-----"""
        cleaned_key = clean_public_key(public_key)
        self.assertEqual(cleaned_key, "fake-public-key")

    def test_public_key_empty(self):
        """Clean empty public key works"""
        public_key = ""
        cleaned_key = clean_public_key(public_key)
        self.assertEqual(cleaned_key, "")

    def test_public_key_with_newline_characters(self):
        """Clean public key with newline characters works"""
        public_key = (
            "-----BEGIN PUBLIC KEY-----\nfake-public-key\n-----END PUBLIC KEY-----"
        )
        cleaned_key = clean_public_key(public_key)
        self.assertEqual(cleaned_key, "fake-public-key")

    def test_public_key_with_carriage_return_characters(self):
        """Clean public key with carriage return characters works"""
        public_key = (
            "-----BEGIN PUBLIC KEY-----\rfake-public-key\r-----END PUBLIC KEY-----"
        )
        cleaned_key = clean_public_key(public_key)
        self.assertEqual(cleaned_key, "fake-public-key")

    def test_public_key_with_mixed_newlines(self):
        """Clean public key with mixed newline and carriage return characters works"""
        public_key = (
            "-----BEGIN PUBLIC KEY-----\r\nfake-public-key\r\n-----END PUBLIC KEY-----"
        )
        cleaned_key = clean_public_key(public_key)
        self.assertEqual(cleaned_key, "fake-public-key")
