# -*- coding: utf-8 -*-
"""
Tests for onadata.apps.main.forms helpers.
"""

from unittest.mock import patch

from django import forms
from django.test import SimpleTestCase, override_settings

import requests

from onadata.apps.main.forms import _assert_url_not_internal, _get_with_ssrf_guard


def _redirect_to(location):
    """Build a 302 response pointing at ``location``."""
    response = requests.Response()
    response.status_code = 302
    response.headers["Location"] = location
    # No underlying connection to release on these synthetic responses.
    response._content_consumed = True  # pylint: disable=protected-access
    return response


class AssertUrlNotInternalTestCase(SimpleTestCase):
    """Tests for the XLSForm-by-URL SSRF guard."""

    def test_rejects_non_http_scheme(self):
        """Only http and https URLs are allowed."""
        with self.assertRaises(forms.ValidationError):
            _assert_url_not_internal("ftp://example.com/form.xlsx")

    def test_rejects_loopback_address(self):
        """A loopback URL is blocked."""
        with self.assertRaises(forms.ValidationError):
            _assert_url_not_internal("http://127.0.0.1/form.xlsx")

    def test_rejects_link_local_metadata_address(self):
        """The cloud metadata endpoint (link-local) is blocked."""
        with self.assertRaises(forms.ValidationError):
            _assert_url_not_internal("http://169.254.169.254/latest/meta-data/")

    def test_rejects_private_address(self):
        """A private RFC 1918 URL is blocked."""
        with self.assertRaises(forms.ValidationError):
            _assert_url_not_internal("http://10.0.0.5/form.xlsx")

    def test_allows_public_address(self):
        """A public IP literal is permitted."""
        _assert_url_not_internal("https://8.8.8.8/form.xlsx")

    @override_settings(XLSFORM_URL_ALLOWED_HOSTS=["127.0.0.1"])
    def test_allowlisted_host_bypasses_check(self):
        """An allowlisted host bypasses the private-address check."""
        _assert_url_not_internal("http://127.0.0.1/form.xlsx")


class GetWithSsrfGuardTestCase(SimpleTestCase):
    """Tests for the per-hop redirect validation in the XLSForm downloader."""

    @patch("onadata.apps.main.forms.requests.get")
    def test_blocks_redirect_to_internal_address(self, mock_get):
        """A public URL that redirects to an internal address is blocked."""
        mock_get.return_value = _redirect_to("http://169.254.169.254/latest/meta-data/")

        with self.assertRaises(forms.ValidationError):
            _get_with_ssrf_guard("https://8.8.8.8/form.xlsx")

        # The internal redirect target is never requested.
        self.assertEqual(mock_get.call_count, 1)

    @patch("onadata.apps.main.forms.requests.get")
    def test_rejects_too_many_redirects(self, mock_get):
        """A redirect loop is capped rather than followed indefinitely."""
        mock_get.return_value = _redirect_to("https://8.8.4.4/form.xlsx")

        with self.assertRaises(forms.ValidationError):
            _get_with_ssrf_guard("https://8.8.8.8/form.xlsx")

    @patch("onadata.apps.main.forms.requests.get")
    def test_returns_non_redirect_response(self, mock_get):
        """A direct (non-redirect) response is returned to the caller."""
        ok_response = requests.Response()
        ok_response.status_code = 200
        mock_get.return_value = ok_response

        self.assertIs(_get_with_ssrf_guard("https://8.8.8.8/form.xlsx"), ok_response)
        self.assertEqual(mock_get.call_count, 1)
