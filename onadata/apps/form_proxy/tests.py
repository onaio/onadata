from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from requests.exceptions import Timeout, ConnectionError as RequestsConnectionError
from .services import FormNotFoundError, OnadataAuthError, OnadataUpstreamError


class FormSubmissionsViewTests(TestCase):
    def setUp(self):
        self.url = reverse("form-submissions", args=[891934])

    @patch("onadata.apps.form_proxy.views.onadata_client.fetch_form_submissions")
    def test_valid_form_returns_json(self, mock_fetch):
        mock_fetch.return_value = [{"id": 1, "value": "test"}]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": 1, "value": "test"}])

    @patch("onadata.apps.form_proxy.views.onadata_client.fetch_form_submissions")
    def test_form_not_found_returns_404(self, mock_fetch):
        mock_fetch.side_effect = FormNotFoundError(891934)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "Form Not Found")

    @patch("onadata.apps.form_proxy.views.onadata_client.fetch_form_submissions")
    def test_auth_error_returns_matching_status(self, mock_fetch):
        mock_fetch.side_effect = OnadataAuthError(403)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    @patch("onadata.apps.form_proxy.views.onadata_client.fetch_form_submissions")
    def test_upstream_error_returns_502(self, mock_fetch):
        mock_fetch.side_effect = OnadataUpstreamError(500)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 502)

    @patch("onadata.apps.form_proxy.views.onadata_client.fetch_form_submissions")
    def test_timeout_returns_504(self, mock_fetch):
        mock_fetch.side_effect = Timeout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 504)

    @patch("onadata.apps.form_proxy.views.onadata_client.fetch_form_submissions")
    def test_connection_error_returns_503(self, mock_fetch):
        mock_fetch.side_effect = RequestsConnectionError()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)