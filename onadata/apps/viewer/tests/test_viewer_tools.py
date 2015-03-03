from django.test.client import RequestFactory

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.viewer_tools import (
    export_def_from_filename,
    generate_enketo_form_defaults,
    get_client_ip)


class TestViewerTools(TestBase):
    def test_export_def_from_filename(self):
        filename = "path/filename.xlsx"
        ext, mime_type = export_def_from_filename(filename)
        self.assertEqual(ext, 'xlsx')
        self.assertEqual(mime_type, 'vnd.openxmlformats')

    def test_get_client_ip(self):
        request = RequestFactory().get("/")
        client_ip = get_client_ip(request)
        self.assertIsNotNone(client_ip)
        # will this always be 127.0.0.1
        self.assertEqual(client_ip, "127.0.0.1")

    def test_get_enketo_defaults_without_vars(self):
        # create xform
        self._publish_transportation_form()
        # create map without variables
        defaults = generate_enketo_form_defaults(self.xform)

        # should return empty default map
        self.assertEqual(defaults, {})

    def test_get_enketo_defaults_with_right_xform(self):
        # create xform
        self._publish_transportation_form()
        # create kwargs with existing xform variable
        xform_variable_name = \
            'available_transportation_types_to_referral_facility'
        xform_variable_value = 'ambulance'
        kwargs = {xform_variable_name: xform_variable_value}
        defaults = generate_enketo_form_defaults(self.xform, **kwargs)

        key = "defaults[%]".format(xform_variable_name)
        self.assertEqual(
            defaults,
            {key: xform_variable_value})

    def test_get_enketo_defaults_with_non_existent_field(self):
        # create xform
        self._publish_transportation_form()
        # create kwargs with NON-existing xform variable
        kwargs = {'name': 'bla'}
        defaults = generate_enketo_form_defaults(self.xform, **kwargs)
        self.assertEqual(defaults, {})
