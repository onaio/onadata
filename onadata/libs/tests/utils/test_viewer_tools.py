# -*- coding: utf-8 -*-
"""Test onadata.libs.utils.viewer_tools."""

import json
import os
from unittest.mock import Mock, patch

from django.core.files.base import File
from django.core.files.temp import NamedTemporaryFile
from django.http import Http404
from django.test import SimpleTestCase
from django.test.client import RequestFactory
from django.test.utils import override_settings
from django.utils import timezone

from onadata.apps.logger.models import Attachment, Instance, XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.exceptions import EnketoError
from onadata.libs.utils.viewer_tools import (
    ENKETO_ERROR_PREFIX,
    ENKETO_GENERIC_ERROR,
    create_attachments_zipfile,
    export_def_from_filename,
    generate_enketo_form_defaults,
    get_client_ip,
    get_form,
    get_form_url,
    handle_enketo_error,
)


class TestViewerTools(TestBase):
    """Test viewer_tools functions."""

    def test_export_def_from_filename(self):
        """Test export_def_from_filename()."""
        filename = "path/filename.xlsx"
        ext, mime_type = export_def_from_filename(filename)
        self.assertEqual(ext, "xlsx")
        self.assertEqual(mime_type, "vnd.openxmlformats")

    def test_get_client_ip(self):
        """Test get_client_ip()."""
        request = RequestFactory().get("/")
        client_ip = get_client_ip(request)
        self.assertIsNotNone(client_ip)
        # will this always be 127.0.0.1
        self.assertEqual(client_ip, "127.0.0.1")

    # pylint: disable=C0103
    def test_get_enketo_defaults_without_vars(self):
        """Test generate_enketo_form_defaults() without vars."""
        # create xform
        self._publish_transportation_form()
        # create map without variables
        defaults = generate_enketo_form_defaults(self.xform)

        # should return empty default map
        self.assertEqual(defaults, {})

    # pylint: disable=C0103
    def test_get_enketo_defaults_with_right_xform(self):
        """Test generate_enketo_form_defaults() with xform vars."""
        # create xform
        self._publish_transportation_form()
        # create kwargs with existing xform variable
        xform_variable_name = "available_transportation_types_to_referral_facility"
        xform_variable_value = "ambulance"
        kwargs = {xform_variable_name: xform_variable_value}
        defaults = generate_enketo_form_defaults(self.xform, **kwargs)

        key = "defaults[/data/transport/{}]".format(xform_variable_name)
        self.assertEqual(defaults, {key: xform_variable_value})

    # pylint: disable=C0103
    def test_get_enketo_defaults_with_multiple_params(self):
        """Test generate_enketo_form_defaults() with multiple params."""
        # create xform
        self._publish_transportation_form()
        # create kwargs with existing xform variable
        transportation_types = "available_transportation_types_to_referral_facility"
        transportation_types_value = "ambulance"

        frequency = "frequency_to_referral_facility"
        frequency_value = "daily"

        kwargs = {
            transportation_types: transportation_types_value,
            frequency: frequency_value,
        }
        defaults = generate_enketo_form_defaults(self.xform, **kwargs)

        transportation_types_key = "defaults[/data/transport/{}]".format(
            transportation_types
        )
        frequency_key = (
            "defaults[/data/transport/"
            "loop_over_transport_types_frequency/"
            "{}/{}]".format(transportation_types_value, frequency)
        )
        self.assertIn(transportation_types_key, defaults)
        self.assertIn(frequency_key, defaults)

    # pylint: disable=C0103
    def test_get_enketo_defaults_with_non_existent_field(self):
        """Test generate_enketo_form_defaults() with non existent field."""
        # create xform
        self._publish_transportation_form()
        # create kwargs with NON-existing xform variable
        kwargs = {"name": "bla"}
        defaults = generate_enketo_form_defaults(self.xform, **kwargs)
        self.assertEqual(defaults, {})

    def test_get_form(self):
        """Test get_form()."""
        # non existent id_string
        with self.assertRaises(Http404):
            get_form({"id_string": "non_existent_form"})

        self._publish_transportation_form()

        # valid xform id_string
        kwarg = {"id_string__iexact": self.xform.id_string}
        xform = get_form(kwarg)
        self.assertIsInstance(xform, XForm)

        # pass a queryset
        kwarg["queryset"] = XForm.objects.all()
        xform = get_form(kwarg)
        self.assertIsInstance(xform, XForm)

        # deleted form
        xform.deleted_at = timezone.now()
        xform.save()
        with self.assertRaises(Http404):
            get_form(kwarg)

    @override_settings(TESTING_MODE=False, ENKETO_PROTOCOL="http")
    def test_get_form_url(self):
        """Test get_form_url()."""
        request = RequestFactory().get("/")

        # explicit https protocol https://ona.io
        url = get_form_url(request, protocol="https")
        self.assertEqual(url, "https://ona.io")

        # with username and explicit https https://ona.io/bob
        url = get_form_url(request, username="bob", protocol="https")
        self.assertEqual(url, "https://ona.io/bob")

        # with http protocol http://ona.io/bob
        url = get_form_url(
            request,
            username="bob",
        )
        self.assertEqual(url, "http://ona.io/bob")

        # preview url http://ona.io/preview/bob
        url = get_form_url(request, username="bob", preview=True)
        self.assertEqual(url, "http://ona.io/preview/bob")

        # with form pk url http://ona.io/bob/1
        url = get_form_url(request, username="bob", xform_pk=1)
        self.assertEqual(url, "http://ona.io/bob/1")

        # with form pk and explicit https url https://ona.io/bob/1
        url = get_form_url(request, username="bob", xform_pk=1, protocol="https")
        self.assertEqual(url, "https://ona.io/bob/1")

        # with form uuid url http://ona.io/enketo/492
        url = get_form_url(request, xform_pk=492, generate_consistent_urls=True)
        self.assertEqual(url, "http://ona.io/enketo/492")

        # with form uuid and explicit https url https://ona.io/enketo/492
        url = get_form_url(
            request, xform_pk=492, generate_consistent_urls=True, protocol="https"
        )
        self.assertEqual(url, "https://ona.io/enketo/492")

    @override_settings(ZIP_REPORT_ATTACHMENT_LIMIT=8)
    @patch("onadata.libs.utils.viewer_tools.report_exception")
    def test_create_attachments_zipfile_file_too_big(self, rpt_mock):
        """
        When a file is larger than what is allowed in settings an exception
        should be raised.
        """
        self._publish_transportation_form_and_submit_instance()
        self.media_file = "1335783522563.jpg"
        media_file = os.path.join(
            self.this_directory,
            "fixtures",
            "transportation",
            "instances",
            self.surveys[0],
            self.media_file,
        )
        self.instance = Instance.objects.all()[0]
        self.attachment = Attachment.objects.create(
            instance=self.instance, media_file=File(open(media_file, "rb"), media_file)
        )
        with NamedTemporaryFile() as zip_file:
            create_attachments_zipfile(Attachment.objects.all(), zip_file)

        message = ("Create attachment zip exception", "File is greater than 8 bytes")

        self.assertTrue(rpt_mock.called)
        rpt_mock.assert_called_with(message[0], message[1])


def _mock_response(status_code, content, text=None):
    """Build a mock response for handle_enketo_error tests."""
    response = Mock()
    response.status_code = status_code
    response.content = content
    response.text = text if text is not None else content.decode("utf-8")
    return response


@patch("onadata.libs.utils.viewer_tools.report_exception")
class TestHandleEnketoError(SimpleTestCase):
    """Test handle_enketo_error() branches."""

    def test_valid_json_with_message_and_status_400(self, mock_report):
        """400 with a JSON message raises EnketoError containing that message."""
        mock_report.return_value = "sentry-id"
        body = json.dumps({"message": "Wrong parameter"}).encode()
        response = _mock_response(400, body)

        with self.assertRaises(EnketoError) as ctx:
            handle_enketo_error(response)

        self.assertIn("Wrong parameter", str(ctx.exception))
        self.assertIn("sentry-id", str(ctx.exception))
        mock_report.assert_called_once_with("HTTP Error 400", "Wrong parameter")

    def test_valid_json_with_message_and_status_500(self, mock_report):
        """Non-400 status with valid JSON raises EnketoError with generic message."""
        mock_report.return_value = "sentry-id"
        body = json.dumps({"message": "Internal failure"}).encode()
        response = _mock_response(500, body)

        with self.assertRaises(EnketoError) as ctx:
            handle_enketo_error(response)

        self.assertIn(ENKETO_GENERIC_ERROR, str(ctx.exception))
        self.assertIn("sentry-id", str(ctx.exception))
        mock_report.assert_called_once_with("HTTP Error 500", "Internal failure")

    def test_valid_json_without_message_key(self, mock_report):
        """Valid JSON missing 'message' key falls back to response.text."""
        mock_report.return_value = "sentry-id"
        body = json.dumps({"error": "unknown"}).encode()
        response = _mock_response(400, body, text="raw response text")

        with self.assertRaises(EnketoError) as ctx:
            handle_enketo_error(response)

        self.assertIn("raw response text", str(ctx.exception))
        mock_report.assert_called_once_with("HTTP Error 400", "raw response text")

    def test_invalid_json_with_status_500(self, mock_report):
        """Invalid JSON + 5xx raises EnketoError with generic message."""
        mock_report.return_value = "sentry-id"
        response = _mock_response(502, b"bad gateway html", text="bad gateway html")

        with self.assertRaises(EnketoError) as ctx:
            handle_enketo_error(response)

        self.assertIn(ENKETO_GENERIC_ERROR, str(ctx.exception))
        self.assertIn("sentry-id", str(ctx.exception))
        mock_report.assert_called_once()

    def test_invalid_json_with_status_400(self, mock_report):
        """Invalid JSON + 400 raises EnketoError with response text as message."""
        mock_report.return_value = "sentry-id"
        response = _mock_response(400, b"not json", text="not json")

        with self.assertRaises(EnketoError) as ctx:
            handle_enketo_error(response)

        self.assertIn("not json", str(ctx.exception))
        self.assertIn("sentry-id", str(ctx.exception))

    def test_invalid_json_with_non_400_non_5xx(self, mock_report):
        """Invalid JSON + non-400/non-5xx raises EnketoError with generic message."""
        mock_report.return_value = "sentry-id"
        response = _mock_response(422, b"unprocessable", text="unprocessable")

        with self.assertRaises(EnketoError) as ctx:
            handle_enketo_error(response)

        self.assertIn(ENKETO_GENERIC_ERROR, str(ctx.exception))

    def test_error_message_includes_enketo_prefix(self, mock_report):
        """All raised errors include the Enketo error prefix."""
        mock_report.return_value = "sentry-id"
        body = json.dumps({"message": "some error"}).encode()
        response = _mock_response(400, body)

        with self.assertRaises(EnketoError) as ctx:
            handle_enketo_error(response)

        self.assertTrue(str(ctx.exception).startswith(ENKETO_ERROR_PREFIX))
