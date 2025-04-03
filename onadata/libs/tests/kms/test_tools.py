"""Tests for onadata.libs.kms.kms_tools"""

from datetime import datetime, timedelta
from datetime import timezone as tz
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from moto import mock_aws

from onadata.apps.logger.models.kms import KMSKey
from onadata.apps.logger.models.xform import create_survey_element_from_dict
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.kms.clients import AWSKMSClient
from onadata.libs.kms.tools import create_key, disable_key, get_kms_client, rotate_key


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
        self.assertIsNone(kms_key.rotated_at)
        self.assertEqual(kms_key.provider, KMSKey.KMSProvider.AWS)
        # Public PEM-encoded key is saved without the header and footer
        self.assertNotIn("-----BEGIN PUBLIC KEY-----", kms_key.public_key)
        self.assertNotIn("-----END PUBLIC KEY-----", kms_key.public_key)

    @override_settings(KMS_ROTATION_DURATION=timedelta(days=365))
    @patch("django.utils.timezone.now")
    def test_rotation_date(self, mock_now):
        """Rotation date is set if duration available."""
        mocked_now = datetime(2025, 4, 2, tzinfo=tz.utc)
        mock_now.return_value = mocked_now
        kms_key = create_key(self.org)

        self.assertEqual(kms_key.next_rotation_at, mocked_now + timedelta(days=365))

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
        new_key = rotate_key(self.kms_key)
        self.kms_key.refresh_from_db()
        self.xform.refresh_from_db()

        # New key is created since rotation of asymmetric is not
        # allowed
        self.assertEqual(KMSKey.objects.all().count(), 2)
        self.assertEqual(new_key.description, "Key-2025-04-03")
        self.assertEqual(new_key.content_type, self.content_type)
        self.assertEqual(new_key.object_id, self.org.pk)
        self.assertIsNotNone(new_key.key_id)
        self.assertIsNotNone(new_key.public_key)
        self.assertIsNone(new_key.rotated_at)
        self.assertEqual(new_key.provider, KMSKey.KMSProvider.AWS)
        self.assertNotIn("-----BEGIN PUBLIC KEY-----", new_key.public_key)
        self.assertNotIn("-----END PUBLIC KEY-----", new_key.public_key)

        # Old key is rotated
        self.assertEqual(self.kms_key.rotated_at, mocked_now)
        self.assertIsNone(self.kms_key.disabled_at)

        # Forms using old key are updated to use new key
        json_dict = self.xform.json_dict()
        json_dict["public_key"] = new_key.public_key
        json_dict["version"] = "202504031220"
        survey = create_survey_element_from_dict(json_dict)

        self.assertEqual(self.xform.version, "202504031220")
        self.assertEqual(self.xform.json, survey.to_json_dict())
        self.assertEqual(self.xform.xml, survey.to_xml())
        self.assertEqual(self.xform.public_key, new_key.public_key)
        self.assertTrue(
            self.xform.kms_keys.filter(
                kms_key=new_key,
                version="202504031220",
            ).exists()
        )

    @patch.object(AWSKMSClient, "disable_key")
    @patch("django.utils.timezone.now")
    def test_rotate_and_disable(self, mock_now, mock_aws_disable):
        """A key can be disabled during rotation."""
        mocked_now = datetime(2025, 4, 3, tzinfo=tz.utc)
        mock_now.return_value = mocked_now

        rotate_key(self.kms_key, disable=True)

        self.kms_key.refresh_from_db()

        self.assertEqual(self.kms_key.disabled_at, mocked_now)

        mock_aws_disable.assert_called_once_with("fake-key-id")


@mock_aws
@override_settings(
    KMS_PROVIDER="AWS",
    AWS_ACCESS_KEY_ID="fake-id",
    AWS_SECRET_ACCESS_KEY="fake-secret",
    AWS_KMS_REGION_NAME="us-east-1",
)
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
    @patch.object(AWSKMSClient, "disable_key")
    def test_disable(self, mock_aws_disable, mock_now):
        """KMSKey is disabled."""
        mocked_now = datetime(2025, 4, 3, 12, 20, tzinfo=tz.utc)
        mock_now.return_value = mocked_now

        disable_key(self.kms_key)

        mock_aws_disable.assert_called_once_with("fake-key-id")

        self.kms_key.refresh_from_db()

        self.assertEqual(self.kms_key.disabled_at, mocked_now)
