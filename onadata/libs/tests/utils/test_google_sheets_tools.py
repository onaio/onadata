import os

from apiclient import discovery
from apiclient.http import HttpMock
from apiclient.http import HttpMockSequence

from mock import patch

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.google_sheets_tools import \
    new_spread_sheets, DISCOVERY_URL, get_spread_sheet, \
    get_spread_sheet_title, add_row_or_column, get_spread_sheet_rows, \
    set_spread_sheet_data, GoogleSheetsExportBuilder, get_spread_sheet_url


class TestGoogleSheetTools(TestBase):
    def setUp(self):
        super(TestGoogleSheetTools, self).setUp()
        # create an xform
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "api", "tests", "fixtures", "forms",
                            "tutorial", "tutorial.xls")
        self._publish_xls_file_and_set_xform(path)
        # make a couple of submissions
        for i in range(1, 3):
            path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                "apps", "api", "tests", "fixtures", "forms",
                                "tutorial", "instances", "{}.xml".format(i))
            self._make_submission(path)

        self.google_folder_path = os.path.join(os.path.dirname(__file__), "..",
                                               "..", "..", "libs", "tests",
                                               "utils", "fixtures", "google")

    def _google_sheet_detail_service(self):
        path = os.path.join(self.google_folder_path,
                            "google_sheet_detail.json")

        http = HttpMock(path, {'status': '200'})
        service = discovery.build('sheets', 'v4', http=http,
                                  discoveryServiceUrl=DISCOVERY_URL)
        return service

    def _google_sheet_add_row_column(self):
        path = os.path.join(self.google_folder_path, "add_row_column.json")

        http = HttpMock(path, {'status': '200'})
        service = discovery.build('sheets', 'v4', http=http,
                                  discoveryServiceUrl=DISCOVERY_URL)
        return service

    @patch('onadata.libs.utils.google_sheets_tools.create_service')
    def test_new_spread_sheets(self, mock_sheet_service):
        service = self._google_sheet_detail_service()
        mock_sheet_service.return_value = service
        google_sheets = GoogleSheetsExportBuilder(self.xform, {},
                                                  {})

        section_details = google_sheets.create_sheets_n_headers()

        response = new_spread_sheets(service, 'weka-sync', section_details)

        self.assertIsNotNone(response)
        spread_sheet_id = "16-58Zf5gDfKwWFywtMOnJVN2PTELjd4Q3yTWAwMA"
        self.assertEqual(response.get('spreadsheetId'), spread_sheet_id)

    def test_get_spread_sheet(self):
        service = self._google_sheet_detail_service()
        spread_sheet_id = "16-58Zf5gDfKwWFywtMOnJVN2PTELjd4Q3yTWAwMA"

        response = get_spread_sheet(service, spread_sheet_id)

        self.assertIsNotNone(response)
        self.assertEqual(response.get('spreadsheetId'), spread_sheet_id)

    def test_get_spread_sheet_title(self):
        service = self._google_sheet_detail_service()
        spread_sheet_id = "16-58Zf5gDfKwWFywtMOnJVN2PTELjd4Q3yTWAwMA"

        response = get_spread_sheet_title(service, spread_sheet_id)

        self.assertIsNotNone(response)
        self.assertEqual("weka-sync", response)

    def test_add_row_or_column(self):
        service = self._google_sheet_add_row_column()
        spread_sheet_id = "16-58Zf5gDfKwWFywtMOnJVN2PTELjd4Q3yTWAwMA"
        sheet_id = 1836938579

        response = add_row_or_column(service, spread_sheet_id, sheet_id,
                                     columns=1, rows=1)
        self.assertIsNotNone(response)
        self.assertEqual(response.get('spreadsheetId'), spread_sheet_id)

    def test_get_spread_sheet_rows(self):
        service = self._google_sheet_detail_service()
        spread_sheet_id = "16-58Zf5gDfKwWFywtMOnJVN2PTELjd4Q3yTWAwMA"

        spread_sheet_details = get_spread_sheet(service, spread_sheet_id)

        path = os.path.join(self.google_folder_path, "spread_sheet_row.json")

        http = HttpMock(path, {'status': '200'})
        service = discovery.build('sheets', 'v4', http=http,
                                  discoveryServiceUrl=DISCOVERY_URL)

        response = get_spread_sheet_rows(service, spread_sheet_details,
                                         row_index=2)
        self.assertIsNotNone(response)
        self.assertEqual(response.get('range'),
                         "select_one_choices_test!A2:R2")

    def test_set_spread_sheet_data(self):
        service = self._google_sheet_detail_service()
        spread_sheet_id = "16-58Zf5gDfKwWFywtMOnJVN2PTELjd4Q3yTWAwMA"
        spread_sheet_details = get_spread_sheet(service, spread_sheet_id)
        path = os.path.join(self.google_folder_path, "set_data.json")

        http = HttpMock(path, {'status': '200'})
        service = discovery.build('sheets', 'v4', http=http,
                                  discoveryServiceUrl=DISCOVERY_URL)
        data = [["44", "2016-05-23T16:16:53.626+03",
                 "2016-05-23T16:17:00.122+03",
                 "2016-05-23", "359297054780555", "",
                 "uuid:db18b4dd-aaf8-417b-b179-ff962c3e3cc8", "3634031",
                 "db18b4dd-aaf8-417b-b179-ff962c3e3cc8", "2016-05-23T13:17:04",
                 "1", "", "-1", "", "", "201605231316", "7"]]

        sections_details = [{
            "title": "sheet1",
            "data": data,
            "index": 2
        }]

        results = set_spread_sheet_data(service, spread_sheet_details,
                                        sections_details)

        self.assertIsNotNone(results)
        self.assertEqual(results.get('updatedCells'), 17)

    def _read_file(self, filename):
        f = open(filename, 'rb')
        data = f.read()
        f.close()
        return data

    @patch('onadata.libs.utils.google_sheets_tools.create_service')
    def test_google_sheet_export(self, mock_sheet_service):
        new_google_sheet_path = self._read_file(os.path.join(
            self.google_folder_path, "google_sheet_detail.json"))
        set_headers = self._read_file(os.path.join(self.google_folder_path,
                                                   "set_data.json"))
        extend_sheet = self._read_file(os.path.join(self.google_folder_path,
                                                    "add_row_column.json"))
        set_data = self._read_file(os.path.join(self.google_folder_path,
                                                "set_data.json"))

        http = HttpMockSequence([
            ({'status': '200'}, new_google_sheet_path),
            ({'status': '200'}, set_headers),
            ({'status': '200'}, extend_sheet),
            ({'status': '200'}, set_data)])
        service = discovery.build('sheets', 'v4', http=http,
                                  discoveryServiceUrl=DISCOVERY_URL)
        mock_sheet_service.return_value = service
        fake_creds = {}
        google_sheets = GoogleSheetsExportBuilder(self.xform, fake_creds)
        data = [["44", "2016-05-23T16:16:53.626+03",
                 "2016-05-23T16:17:00.122+03",
                 "2016-05-23", "359297054780555", "",
                 "uuid:db18b4dd-aaf8-417b-b179-ff962c3e3cc8", "3634031",
                 "db18b4dd-aaf8-417b-b179-ff962c3e3cc8", "2016-05-23T13:17:04",
                 "1", "", "-1", "", "", "201605231316", "7"]]
        url = google_sheets.export(data)

        spread_sheet_id = "16-58Zf5gDfKwWFywtMOnJVN2PTELjd4Q3yTWAwMA"
        expected_url = get_spread_sheet_url(spread_sheet_id)

        self.assertEqual(url, expected_url)

    @patch('onadata.libs.utils.google_sheets_tools.create_service')
    def test_google_sheet_live_update(self, mock_sheet_service):
        get_google_sheet = self._read_file(os.path.join(
            self.google_folder_path, "google_sheet_detail.json"))
        add_row_column = self._read_file(os.path.join(self.google_folder_path,
                                                      "add_row_column.json"))
        set_headers = self._read_file(os.path.join(self.google_folder_path,
                                                   "set_data.json"))
        set_data = self._read_file(os.path.join(self.google_folder_path,
                                                "set_data.json"))

        http = HttpMockSequence([
            ({'status': '200'}, get_google_sheet),
            ({'status': '200'}, add_row_column),
            ({'status': '200'}, set_headers),
            ({'status': '200'}, set_data)])
        service = discovery.build('sheets', 'v4', http=http,
                                  discoveryServiceUrl=DISCOVERY_URL)
        mock_sheet_service.return_value = service
        fake_creds = {}
        spread_sheet_id = "16-58Zf5gDfKwWFywtMOnJVN2PTELjd4Q3yTWAwMA"

        google_sheets = GoogleSheetsExportBuilder(self.xform, fake_creds)
        data = [["44", "2016-05-23T16:16:53.626+03",
                 "2016-05-23T16:17:00.122+03",
                 "2016-05-23", "359297054780555", "",
                 "uuid:db18b4dd-aaf8-417b-b179-ff962c3e3cc8", "3634031",
                 "db18b4dd-aaf8-417b-b179-ff962c3e3cc8", "2016-05-23T13:17:04",
                 "1", "", "-1", "", "", "201605231316", "7"]]
        google_sheets.live_update(data, spread_sheet_id)

        expected_url = get_spread_sheet_url(spread_sheet_id)
        self.assertEqual(google_sheets.url, expected_url)
