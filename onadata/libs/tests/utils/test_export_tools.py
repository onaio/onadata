import os
from datetime import date, datetime
from django.core.files.storage import default_storage

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import XForm
from onadata.apps.viewer.models.export import Export

from onadata.libs.utils.export_tools import (
    encode_if_str,
    get_attachment_xpath,
    generate_osm_export,
    should_create_new_export,
    parse_request_export_options)
from onadata.apps.logger.models import Attachment
from onadata.apps.api import tests as api_tests


class TestExportTools(TestBase):

    def _create_old_export(self, xform, export_type, options):
        Export(xform=xform, export_type=export_type, options=options).save()
        self.export = Export.objects.filter(
            xform=xform, export_type=export_type)

    def test_invalid_date_format_is_caught(self):
        row = {"date": date(0201, 9, 9)}
        with self.assertRaises(Exception) as error:
            encode_if_str(row, "date", True)

        self.assertEqual(error.exception.message,
                         u'0129-09-09 has an invalid date format')

        row = {"date": date(2001, 9, 9)}
        date_str = encode_if_str(row, "date", True)
        self.assertEqual(date_str, '2001-09-09')

    def test_invalid_datetime_format_is_caught(self):
        row = {"datetime": datetime(0201, 9, 9)}
        with self.assertRaises(Exception) as error:
            encode_if_str(row, "datetime", True)

        self.assertEqual(error.exception.message,
                         u'0129-09-09 00:00:00 has an invalid datetime format')

        row = {"datetime": datetime(2001, 9, 9)}
        date_str = encode_if_str(row, "datetime", True)
        self.assertEqual(date_str, '2001-09-09T00:00:00')

    def test_generate_osm_export(self):
        filenames = [
            'OSMWay234134797.osm',
            'OSMWay34298972.osm',
        ]
        osm_fixtures_dir = os.path.realpath(os.path.join(
            os.path.dirname(api_tests.__file__), 'fixtures', 'osm'))
        paths = [
            os.path.join(osm_fixtures_dir, filename)
            for filename in filenames]
        xlsform_path = os.path.join(osm_fixtures_dir, 'osm.xlsx')
        combined_osm_path = os.path.join(osm_fixtures_dir, 'combined.osm')
        self._publish_xls_file_and_set_xform(xlsform_path)
        submission_path = os.path.join(osm_fixtures_dir, 'instance_a.xml')
        count = Attachment.objects.filter(extension='osm').count()
        self._make_submission_w_attachment(submission_path, paths)
        self.assertTrue(
            Attachment.objects.filter(extension='osm').count() > count)

        options = {"extension": Attachment.OSM}

        export = generate_osm_export(
            Attachment.OSM,
            self.user.username,
            self.xform.id_string,
            None,
            options)
        self.assertTrue(export.is_successful)
        with open(combined_osm_path) as f:
            osm = f.read()
            with default_storage.open(export.filepath) as f2:
                content = f2.read()
                self.assertMultiLineEqual(content.strip(), osm.strip())

    def test_should_create_new_export(self):
        # should only create new export if filter is defined
        # Test setup
        export_type = "csv"
        options = {"group_delimiter": "."}
        self._publish_transportation_form_and_submit_instance()

        will_create_new_export = should_create_new_export(
            self.xform, export_type, options)

        self.assertTrue(will_create_new_export)

    def test_should_not_create_new_export_when_old_exists(self):
        export_type = "csv"
        self._publish_transportation_form_and_submit_instance()
        options = {"group_delimiter": "/",
                   "remove_group_name": False,
                   "split_select_multiples": True}
        self._create_old_export(self.xform, export_type, options)

        will_create_new_export = should_create_new_export(
            self.xform, export_type, options)

        self.assertFalse(will_create_new_export)

    def test_should_create_new_export_when_filter_defined(self):
        export_type = "csv"
        options = {"group_delimiter": "/",
                   "remove_group_name": False,
                   "split_select_multiples": True}

        self._publish_transportation_form_and_submit_instance()
        self._create_old_export(self.xform, export_type, options)

        # Call should_create_new_export with updated options
        options['remove_group_name'] = True

        will_create_new_export = should_create_new_export(
            self.xform, export_type, options)

        self.assertTrue(will_create_new_export)

    def test_should_get_attachment_xpath_with_no_photos(self):
        self._publish_xls_file(os.path.join(self.this_directory, "fixtures",
                                            "photos", "tutorial.xls"))
        filename = "filename"
        dd = XForm.objects.order_by('pk').reverse()[0].data_dictionary()
        row = {}
        get_attachment_xpath(filename, row, dd)

    def test_parse_request_export_options(self):

        request = self.factory.\
            get('/export_async',
                data={"do_not_split_select_multiples": "false"})

        options = parse_request_export_options(request)

        self.assertEqual(options['split_select_multiples'], False)
