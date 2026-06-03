# -*- coding: utf-8 -*-
"""
Tests for the RFC 6266 Content-Disposition parser.
"""

from django.test import SimpleTestCase

from onadata.apps.main.forms import get_filename
from onadata.libs.utils.content_disposition import (
    ContentDispositionError,
    parse_filename,
    secure_filename,
)


class _FakeResponse:
    """Minimal stand-in exposing the ``headers`` attribute ``get_filename`` reads."""

    def __init__(self, content_disposition=None):
        self.headers = {}
        if content_disposition is not None:
            self.headers["Content-Disposition"] = content_disposition


class ParseFilenameTestCase(SimpleTestCase):
    """Tests for :func:`parse_filename`."""

    def test_plain_unquoted_filename(self):
        self.assertEqual(parse_filename("attachment; filename=form.xls"), "form.xls")

    def test_quoted_filename(self):
        self.assertEqual(
            parse_filename('attachment; filename="form.xlsx"'), "form.xlsx"
        )

    def test_quoted_filename_with_escaped_quote(self):
        self.assertEqual(parse_filename('attachment; filename="a\\"b.xml"'), 'a"b.xml')

    def test_extended_utf8_percent_decoded(self):
        self.assertEqual(
            parse_filename("attachment; filename*=UTF-8''my%20form.xlsx"),
            "my form.xlsx",
        )

    def test_extended_utf8_multibyte(self):
        self.assertEqual(
            parse_filename("attachment; filename*=UTF-8''%E2%82%ac-rate.csv"),
            "€-rate.csv",
        )

    def test_extended_iso8859_1(self):
        self.assertEqual(
            parse_filename("attachment; filename*=ISO-8859-1''%A3rates.xls"),
            "\xa3rates.xls",
        )

    def test_extended_iso8859_1_control_char_is_rejected(self):
        with self.assertRaises(ContentDispositionError):
            parse_filename("attachment; filename*=ISO-8859-1''%7Frates.xls")

    def test_extended_form_takes_precedence_over_plain(self):
        # RFC 6266 §4.3: recipients prefer ``filename*`` when both are present.
        self.assertEqual(
            parse_filename(
                "attachment; filename=plain.xlsx; filename*=UTF-8''extended.csv"
            ),
            "extended.csv",
        )

    def test_rfc2231_continuation_is_combined(self):
        self.assertEqual(
            parse_filename('attachment; filename*0="long"; filename*1="name.csv"'),
            "longname.csv",
        )

    def test_no_filename_returns_none(self):
        self.assertIsNone(parse_filename("attachment"))
        self.assertIsNone(parse_filename("inline"))

    def test_path_separators_are_stripped(self):
        self.assertEqual(
            parse_filename('attachment; filename="../../etc/passwd"'),
            ".._.._etc_passwd",
        )

    def test_malformed_header_raises(self):
        # Does not start with a disposition-type token.
        with self.assertRaises(ContentDispositionError):
            parse_filename("=oops")

    def test_duplicate_parameter_raises(self):
        with self.assertRaises(ContentDispositionError):
            parse_filename('attachment; filename="a.csv"; filename="b.csv"')

    def test_unsupported_charset_raises(self):
        with self.assertRaises(ContentDispositionError):
            parse_filename("attachment; filename*=Shift_JIS''x.csv")


class GetFilenameTestCase(SimpleTestCase):
    """Tests for :func:`onadata.apps.main.forms.get_filename`."""

    def test_no_content_disposition_returns_empty(self):
        self.assertEqual(get_filename(_FakeResponse()), "")

    def test_allowed_extension_is_returned(self):
        response = _FakeResponse('attachment; filename="form.xlsx"')
        self.assertEqual(get_filename(response), "form.xlsx")

    def test_disallowed_extension_is_dropped(self):
        response = _FakeResponse('attachment; filename="malware.exe"')
        self.assertEqual(get_filename(response), "")

    def test_path_separators_are_neutralised(self):
        # secure_filename collapses separators to underscores, so the returned
        # name carries no traversal sequence.
        response = _FakeResponse('attachment; filename="../../uploads/form.xlsx"')
        result = get_filename(response)
        self.assertEqual(result, ".._.._uploads_form.xlsx")
        self.assertNotIn("/", result)
        self.assertNotIn("\\", result)

    def test_malformed_header_returns_empty(self):
        # A header that cannot be parsed must not raise out of get_filename.
        response = _FakeResponse("=oops")
        self.assertEqual(get_filename(response), "")


class SecureFilenameTestCase(SimpleTestCase):
    """Tests for :func:`secure_filename`."""

    def test_separators_replaced(self):
        self.assertEqual(secure_filename("a/b\\c.csv"), "a_b_c.csv")

    def test_plain_name_unchanged(self):
        self.assertEqual(secure_filename("form.xlsx"), "form.xlsx")
