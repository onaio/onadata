"""Tests for onadata.libs.kms.kms_tools"""

from datetime import datetime, timedelta
from datetime import timezone as tz
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from moto import mock_aws

from onadata.apps.logger.models.kms import KMSKey
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.kms.clients import AWSKMSClient
from onadata.libs.kms.tools import create_key, get_kms_client


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
