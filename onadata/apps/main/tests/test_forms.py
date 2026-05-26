# -*- coding: utf-8 -*-
"""
Tests for onadata.apps.main.forms helpers.
"""

from django import forms
from django.test import SimpleTestCase, override_settings

from onadata.apps.main.forms import _assert_url_not_internal


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
