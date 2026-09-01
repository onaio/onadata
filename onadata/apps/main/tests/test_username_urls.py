# -*- coding: utf-8 -*-
"""Tests for username-scoped URL routing.

The ``username`` group in ``main/urls.py`` and the API ``users``/``profiles``
routes share ``USERNAME_LOOKUP_REGEX``; these tests pin which usernames the
routes accept and how format suffixes are split off.
"""

from django.test import SimpleTestCase
from django.urls import Resolver404, resolve, reverse


class TestUsernameUrls(SimpleTestCase):
    """Username-scoped URLs accept every username shape the lookup pattern
    allows, reject metacharacters, and split off format suffixes."""

    def test_download_xform_reverse_with_hyphenated_username(self):
        """download_xform reverses for a hyphenated username (id_string and pk)."""
        url = reverse(
            "download_xform",
            kwargs={"username": "alpha-project", "id_string": "myform"},
        )
        self.assertIn("alpha-project", url)

        url_pk = reverse(
            "download_xform",
            kwargs={"username": "alpha-project", "pk": 885480},
        )
        self.assertIn("alpha-project", url_pk)

    def test_username_scoped_urls_reverse_with_hyphenated_username(self):
        """A representative set of username-scoped URLs reverse with a hyphen."""
        username = "alpha-project"
        cases = [
            ("form-list", {"username": username}),
            ("submissions", {"username": username}),
            ("download_xlsform", {"username": username, "id_string": "myform"}),
            ("download_jsonform", {"username": username, "id_string": "myform"}),
            ("enter_data", {"username": username, "id_string": "myform"}),
            ("data-view", {"username": username, "id_string": "myform"}),
            ("manifest-url", {"username": username, "pk": 885480}),
            (
                "export-download",
                {
                    "username": username,
                    "id_string": "myform",
                    "export_type": "csv",
                    "filename": "data.csv",
                },
            ),
        ]
        for name, kwargs in cases:
            with self.subTest(url=name):
                self.assertIn(username, reverse(name, kwargs=kwargs))

    def test_metacharacter_username_does_not_match_routes(self):
        """Usernames with HTML metacharacters do not match username routes.

        The username group uses USERNAME_LOOKUP_REGEX (not the looser
        ``[^/]+``), so characters such as ``<>"'`` that cannot appear in a
        valid username never reach the underlying views.
        """
        for path in ("/<script>/formList", '/a"b/submission', "/a'b/formUpload"):
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path)

    def test_format_suffix_splits_off_email_username(self):
        """``users/<email>.<format>`` resolves to the email plus a ``format``
        kwarg, and the bare email still resolves as the whole username."""
        email = "jane@mail.example.com"
        for suffix in ("json", "xml", "csv", "jsonp", "yaml", "html", "api"):
            with self.subTest(suffix=suffix):
                match = resolve(f"/api/v1/users/{email}.{suffix}")
                self.assertEqual(match.view_name, "user-detail")
                self.assertEqual(match.kwargs, {"username": email, "format": suffix})

        match = resolve(f"/api/v1/users/{email}")
        self.assertEqual(match.kwargs, {"username": email})
