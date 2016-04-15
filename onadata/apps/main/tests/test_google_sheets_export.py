import csv
import os

from oauth2client.client import AccessTokenCredentials

from django.core.files.storage import get_storage_class
from django.core.files.temp import NamedTemporaryFile
from django.utils.dateparse import parse_datetime
from mock import Mock, patch

from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.export_tools import generate_export
from onadata.libs.utils.google_sheets import SheetsClient
from test_base import TestBase


class MockCell():
    def __init__(self, row, col, value):
        self.row = row
        self.col = col
        self.value = value


class TestExport(TestBase):

    def setUp(self):
        # Files that contain the expected spreadsheet data.
        self.fixture_dir = os.path.join(
            self.this_directory, 'fixtures', 'google_sheets_export')

        # Create a test user and login.
        self._create_user_and_login()

        # Create a test submission.
        path = os.path.join(self.fixture_dir, 'tutorial_w_repeats.xls')
        self._publish_xls_file_and_set_xform(path)
        path = os.path.join(self.fixture_dir, 'tutorial_w_repeats.xml')
        self._submission_time = parse_datetime('2013-02-18 15:54:01Z')
        self._make_submission(
            path, forced_submission_time=self._submission_time)

    def _mock_worksheet(self, csv_writer):
        """Creates a mock worksheet object with append_row and insert_row
        methods writing to csv_writer."""
        worksheet = Mock()
        worksheet.append_row.side_effect = \
            lambda values: csv_writer.writerow(values)

        def create_cell(r, c):
            return MockCell(r, c, None)
        worksheet.cell.side_effect = create_cell
        worksheet.update_cells.side_effect = \
            lambda cells: csv_writer.writerow([cell.value for cell in cells])
        worksheet.insert_row.side_effect = \
            lambda values, index: csv_writer.writerow(values)
        return worksheet

    def _mock_spreadsheet(self, csv_writers):
        spreadsheet = Mock()
        spreadsheet.add_worksheet.side_effect = \
            [self._mock_worksheet(writer) for writer in csv_writers]
        return spreadsheet

    def _setup_result_files(self, expected_file_names):
        expected_files = [open(os.path.join(self.fixture_dir, f))
                          for f in expected_file_names]
        result_files = [NamedTemporaryFile() for f in expected_file_names]
        csv_writers = \
            [csv.writer(f, lineterminator='\n') for f in result_files]
        return expected_files, result_files, csv_writers

    def assertStorageExists(self, export):
        storage = get_storage_class()()
        self.assertTrue(storage.exists(export.filepath))
        _, ext = os.path.splitext(export.filename)
        self.assertEqual(ext, '.gsheets')

    def assertEqualExportFiles(self, expected_files, result_files, export):
        for result, expected in zip(result_files, expected_files):
            result.flush()
            result.seek(0)
            expected_content = expected.read()
            # Fill in the actual export id (varies based on test order)
            expected_content = expected_content.replace('###VERSION###',
                                                        str(export.xform
                                                            .version))
            result_content = result.read()
            self.assertEquals(result_content, expected_content)

    @patch.object(SheetsClient, 'new')
    @patch.object(SheetsClient, 'add_service_account_to_spreadsheet')
    @patch.object(SheetsClient, 'get_worksheets_feed')
    @patch('urllib2.urlopen')
    def test_gsheets_export_output(self,
                                   mock_urlopen,
                                   mock_get_worksheets,
                                   mock_account_add_service_account,
                                   mock_new):
        expected_files, result_files, csv_writers = self._setup_result_files(
            ['expected_tutorial_w_repeats.csv'
             ])
        mock_urlopen.return_value.read.return_value = '{"access_token": "baz"}'
        mock_new.return_value = self._mock_spreadsheet(csv_writers)

        options = {
            "split_select_multiples": True,
            "binary_select_multiples": False,
            "google_credentials": AccessTokenCredentials("fake_token",
                                                         user_agent="onaio")
        }

        # Test Google Sheets export.
        export = generate_export(export_type=Export.GOOGLE_SHEETS_EXPORT,
                                 xform=self.xform,
                                 options=options)
        self.assertStorageExists(export)
        self.assertEqualExportFiles(expected_files, result_files, export)
