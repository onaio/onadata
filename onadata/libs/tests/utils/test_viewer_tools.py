# -*- coding: utf-8 -*-
"""Test onadata.libs.utils.viewer_tools."""
import os
from unittest.mock import patch

from django.core.files.base import File
from django.core.files.temp import NamedTemporaryFile
from django.http import Http404
from django.test.client import RequestFactory
from django.test.utils import override_settings
from django.utils import timezone

from onadata.apps.logger.models import Attachment, Instance, XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.viewer_tools import (
    create_attachments_zipfile,
    export_def_from_filename,
    generate_enketo_form_defaults,
    get_client_ip,
    get_form,
    get_form_url,
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

    @override_settings(TESTING_MODE=False)
    def test_get_form_url(self):
        """Test get_form_url()."""
        request = RequestFactory().get("/")

        # default https://ona.io
        url = get_form_url(request)
        self.assertEqual(url, "https://ona.io")

        # with username https://ona.io/bob
        url = get_form_url(request, username="bob")
        self.assertEqual(url, "https://ona.io/bob")

        # with http protocol http://ona.io/bob
        url = get_form_url(request, username="bob", protocol="http")
        self.assertEqual(url, "http://ona.io/bob")

        # preview url http://ona.io/preview/bob
        url = get_form_url(request, username="bob", protocol="http", preview=True)
        self.assertEqual(url, "http://ona.io/preview/bob")

        # with form pk url http://ona.io/bob/1
        url = get_form_url(request, username="bob", xform_pk=1)
        self.assertEqual(url, "https://ona.io/bob/1")

        # with form uuid url https://ona.io/enketo/492
        url = get_form_url(request, xform_pk=492, generate_consistent_urls=True)
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
