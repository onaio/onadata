# -*- coding: utf-8 -*-
"""
Test onadata.libs.serializers.fields.format_suffix_hyperlink_field
"""

from rest_framework.test import APIRequestFactory

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.libs.serializers.fields.format_suffix_hyperlink_field import (
    FormatSuffixHyperlinkedRelatedField,
)


class TestFormatSuffixHyperlinkedRelatedField(TestAbstractViewSet):
    """Test FormatSuffixHyperlinkedRelatedField strips format suffixes correctly."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self._login_user_and_profile()

    def test_strips_json_format_suffix(self):
        """Test that .json suffix is stripped from URLs."""
        request = self.factory.get("/", **self.extra)
        request.user = self.user

        field = FormatSuffixHyperlinkedRelatedField(
            view_name="user-detail",
            lookup_field="username",
            queryset=self.user.__class__.objects.all(),
        )
        field._context = {"request": request}

        url = f"http://testserver/api/v1/users/{self.user.username}.json"
        result = field.to_internal_value(url)
        self.assertEqual(result, self.user)

    def test_strips_various_format_suffixes(self):
        """Test that various format suffixes are stripped."""
        request = self.factory.get("/", **self.extra)
        request.user = self.user

        field = FormatSuffixHyperlinkedRelatedField(
            view_name="user-detail",
            lookup_field="username",
            queryset=self.user.__class__.objects.all(),
        )
        field._context = {"request": request}

        suffixes = ["json", "api", "csv", "jsonp"]
        for suffix in suffixes:
            url = f"http://testserver/api/v1/users/{self.user.username}.{suffix}"
            result = field.to_internal_value(url)
            self.assertEqual(
                result,
                self.user,
                f"Failed to strip .{suffix} format suffix",
            )

    def test_case_insensitive_format_suffix_stripping(self):
        """Test that format suffixes are stripped case-insensitively."""
        request = self.factory.get("/", **self.extra)
        request.user = self.user

        field = FormatSuffixHyperlinkedRelatedField(
            view_name="user-detail",
            lookup_field="username",
            queryset=self.user.__class__.objects.all(),
        )
        field._context = {"request": request}

        # Test uppercase
        url = f"http://testserver/api/v1/users/{self.user.username}.JSON"
        result = field.to_internal_value(url)
        self.assertEqual(result, self.user)

        # Test mixed case
        url = f"http://testserver/api/v1/users/{self.user.username}.Json"
        result = field.to_internal_value(url)
        self.assertEqual(result, self.user)

    def test_strips_format_suffix_with_query_params(self):
        """Test that format suffixes are stripped when URL has query params."""
        request = self.factory.get("/", **self.extra)
        request.user = self.user

        field = FormatSuffixHyperlinkedRelatedField(
            view_name="user-detail",
            lookup_field="username",
            queryset=self.user.__class__.objects.all(),
        )
        field._context = {"request": request}

        url = f"http://testserver/api/v1/users/{self.user.username}.json?foo=bar"
        result = field.to_internal_value(url)
        self.assertEqual(result, self.user)

    def test_preserves_url_without_format_suffix(self):
        """Test that URLs without format suffixes work correctly."""
        request = self.factory.get("/", **self.extra)
        request.user = self.user

        field = FormatSuffixHyperlinkedRelatedField(
            view_name="user-detail",
            lookup_field="username",
            queryset=self.user.__class__.objects.all(),
        )
        field._context = {"request": request}

        url = f"http://testserver/api/v1/users/{self.user.username}"
        result = field.to_internal_value(url)
        self.assertEqual(result, self.user)
