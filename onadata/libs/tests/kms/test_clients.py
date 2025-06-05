"""Tests for module onadata.libs.kms.clients"""

from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from moto import mock_aws
from valigetta.exceptions import InvalidAPIURLException

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
    KMS_API_CLIENT_ID="test-client-id",
    KMS_API_CLIENT_SECRET="test-client-secret",
    KMS_API_URLS={
        "token": "https://api.example.com/token",
        "token_refresh": "https://api.example.com/token/refresh",
        "create_key": "https://api.example.com/api/v1/keys",
        "decrypt": "https://api.example.com/api/v1/keys/{key_id}/decrypt",
        "get_public_key": "https://api.example.com/api/v1/keys/{key_id}",
        "describe_key": "https://api.example.com/api/v1/keys/{key_id}",
        "update_key_description": "https://api.example.com/api/v1/keys/{key_id}",
        "disable_key": "https://api.example.com/api/v1/keys/{key_id}/disable",
        "create_alias": "https://api.example.com/api/v1/keys/{key_id}",
    },
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

        self.assertEqual(client.client_id, "test-client-id")
        self.assertEqual(client.client_secret, "test-client-secret")
        self.assertEqual(client.urls["token"], "https://api.example.com/token")
        self.assertEqual(
            client.urls["token_refresh"], "https://api.example.com/token/refresh"
        )
        self.assertEqual(
            client.urls["create_key"], "https://api.example.com/api/v1/keys"
        )
        self.assertEqual(
            client.urls["decrypt"],
            "https://api.example.com/api/v1/keys/{key_id}/decrypt",
        )
        self.assertEqual(
            client.urls["get_public_key"],
            "https://api.example.com/api/v1/keys/{key_id}",
        )
        self.assertEqual(
            client.urls["describe_key"], "https://api.example.com/api/v1/keys/{key_id}"
        )
        self.assertEqual(
            client.urls["update_key_description"],
            "https://api.example.com/api/v1/keys/{key_id}",
        )
        self.assertEqual(
            client.urls["disable_key"],
            "https://api.example.com/api/v1/keys/{key_id}/disable",
        )
        self.assertEqual(
            client.urls["create_alias"],
            "https://api.example.com/api/v1/keys/{key_id}",
        )

    @patch("onadata.libs.kms.clients.APIKMSClient._validate_urls")
    def test_invalid_urls(self, mock_validate_urls, mock_get_token):
        """Exception is raised if invalid urls are provided."""
        mock_get_token.return_value = {
            "access": "test-access-token",
            "refresh": "test-refresh-token",
        }
        mock_validate_urls.side_effect = InvalidAPIURLException

        with self.assertRaises(ImproperlyConfigured):
            APIKMSClient()
