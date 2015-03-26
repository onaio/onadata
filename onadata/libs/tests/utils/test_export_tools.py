import os
from datetime import date, datetime
from django.core.files.storage import default_storage

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.export_tools import encode_if_str
from onadata.libs.utils.export_tools import generate_osm_export
from onadata.apps.logger.models import Attachment
from onadata.apps.api import tests as api_tests


class TestExportTools(TestBase):

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
        export = generate_osm_export(Attachment.OSM, Attachment.OSM,
                                     self.user.username, self.xform.id_string)
        self.assertTrue(export.is_successful)
        with open(combined_osm_path) as f:
            osm = f.read()
            with default_storage.open(export.filepath) as f2:
                content = f2.read()
                self.assertMultiLineEqual(content, osm)
