"""Tests for module onadata.libs.kms.clients"""

from unittest.mock import patch

from django.test import override_settings

from moto import mock_aws

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.kms.clients import APIKMSClient, AWSKMSClient


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


@override_settings(
    KMS_API_BASE_URL="https://api.example.com",
    KMS_API_CLIENT_ID="test-client-id",
    KMS_API_CLIENT_SECRET="test-client-secret",
)
@patch("onadata.libs.kms.clients.APIKMSClient._get_token")
class APIKMSClientTestBase(TestBase):
    """Tests for APIKMSClient"""

    def test_client_instance(self, mock_get_token):
        """Client instance is initialised with settings."""
        mock_get_token.return_value = {
            "access": "test-access-token",
            "refresh": "test-refresh-token",
        }
        client = APIKMSClient()

        self.assertEqual(client.base_url, "https://api.example.com")
        self.assertEqual(client.client_id, "test-client-id")
        self.assertEqual(client.client_secret, "test-client-secret")
