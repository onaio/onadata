"""Tests for module onadata.libs.kms.clients"""

from django.test import override_settings

from moto import mock_aws

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.kms.clients import AWSKMSClient


@mock_aws
@override_settings(
    AWS_ACCESS_KEY_ID="fake-id",
    AWS_SECRET_ACCESS_KEY="fake-secret",
    AWS_KMS_REGION_NAME="us-east-1",
)
class AWSKMSClientTestBase(TestBase):
    """Tests for AWSKMSClient"""

    def test_client_instance(self):
        """Client instance is initialised with settings."""
        client = AWSKMSClient()

        self.assertEqual(client.aws_access_key_id, "fake-id")
        self.assertEqual(client.aws_secret_access_key, "fake-secret")
        self.assertEqual(client.region_name, "us-east-1")

    @override_settings(
        AWS_ACCESS_KEY_ID="fake-id",
        AWS_SECRET_ACCESS_KEY="fake-secret",
        AWS_KMS_ACCESS_KEY_ID="kms-id",
        AWS_KMS_SECRET_ACCESS_KEY="kms-secret",
        AWS_KMS_REGION_NAME="us-east-1",
    )
    def test_kms_specific_creds(self):
        """KMS specific credentials take precedence."""
        client = AWSKMSClient()

        self.assertEqual(client.aws_access_key_id, "kms-id")
        self.assertEqual(client.aws_secret_access_key, "kms-secret")
        self.assertEqual(client.region_name, "us-east-1")

    def test_create_key(self):
        """KMS key is created"""

        client = AWSKMSClient()

        metadata = client.create_key("Key-2025-04-02")

        self.assertIn("key_id", metadata)
        self.assertIn("public_key", metadata)
