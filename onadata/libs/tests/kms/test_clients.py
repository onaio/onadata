"""Tests for module onadata.libs.kms.clients"""

from unittest.mock import Mock, patch

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

import requests
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
@patch("boto3.client")
class AWSKMSClientTestBase(TestBase):
    """Tests for AWSKMSClient"""

    def test_client_instance(self, mock_boto3_client):
        """Client instance is initialised with settings."""
        mock_aws_kms_client = Mock()
        mock_boto3_client.return_value = mock_aws_kms_client

        client = AWSKMSClient()

        mock_boto3_client.assert_called_once_with(
            "kms",
            aws_access_key_id="fake-id",
            aws_secret_access_key="fake-secret",
            region_name="us-east-1",
        )
        self.assertIs(client.boto3_client, mock_aws_kms_client)

    @override_settings(
        AWS_ACCESS_KEY_ID="fake-id",
        AWS_SECRET_ACCESS_KEY="fake-secret",
        AWS_KMS_ACCESS_KEY_ID="kms-id",
        AWS_KMS_SECRET_ACCESS_KEY="kms-secret",
        AWS_KMS_REGION_NAME="us-east-1",
    )
    def test_kms_specific_creds(self, mock_boto3_client):
        """KMS specific credentials take precedence."""
        AWSKMSClient()

        mock_boto3_client.assert_called_once_with(
            "kms",
            aws_access_key_id="kms-id",
            aws_secret_access_key="kms-secret",
            region_name="us-east-1",
        )


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
class APIKMSClientTestBase(TestBase):
    """Tests for APIKMSClient"""

    def setUp(self):
        super().setUp()
        cache.clear()

    @patch("requests.post")
    def test_client_instance(self, mock_post):
        """Client instance is initialised with settings."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access": "test-access-token",
            "refresh": "test-refresh-token",
        }
        mock_post.return_value = mock_response

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

    @patch("requests.post")
    @patch("onadata.libs.kms.clients.APIKMSClient._validate_urls")
    def test_invalid_urls(self, mock_validate_urls, mock_post):
        """Exception is raised if invalid urls are provided."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access": "test-access-token",
            "refresh": "test-refresh-token",
        }
        mock_post.return_value = mock_response
        mock_validate_urls.side_effect = InvalidAPIURLException

        with self.assertRaises(ImproperlyConfigured):
            APIKMSClient()

    def test_saved_token_is_used(self):
        """Saved token is used to initialise the client."""
        cache.set(
            "kms-token",
            {"access": "cached-access-token", "refresh": "cached-refresh-token"},
        )
        client = APIKMSClient()

        self.assertEqual(client.access_token, "cached-access-token")
        self.assertEqual(client.refresh_token, "cached-refresh-token")

    @patch("requests.post")
    def test_token_saved_on_refresh(self, mock_post):
        """Token is saved on refresh."""
        cache.set(
            "kms-token",
            {"access": "cached-access-token", "refresh": "cached-refresh-token"},
        )
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access": "test-access-token",
            "refresh": "test-refresh-token",
        }
        mock_post.return_value = mock_response

        client = APIKMSClient()
        client._on_token_refresh(mock_response.json())

        self.assertEqual(cache.get("kms-token"), mock_response.json())
