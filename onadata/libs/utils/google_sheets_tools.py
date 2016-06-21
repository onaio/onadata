import httplib2

from apiclient import discovery

from onadata.libs.utils.export_tools import (
    ExportBuilder,
    dict_to_joined_export,
    encode_if_str
)
from onadata.libs.utils.common_tags import INDEX, PARENT_INDEX

DISCOVERY_URL = "https://sheets.googleapis.com/$discovery/rest?version=v4"
SHEETS_BASE_URL = 'https://docs.google.com/spreadsheet/ccc?key=%s&hl'


def create_service(credentials):
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('sheets', 'v4', http=http,
                              discoveryServiceUrl=DISCOVERY_URL)
    return service


def create_drive_folder(credentials, title="weka"):
    http = httplib2.Http()
    drive = discovery.build("drive", "v3", http=credentials.authorize(http))

    file_metadata = {
        'name': title,
        'mimeType': 'application/vnd.google-apps.folder'
    }

    drive.files().create(body=file_metadata, fields='id').execute()


def get_sheets_folder_id(credentials, folder_name="onadata"):
    http = httplib2.Http()
    drive = discovery.build("drive", "v3", http=credentials.authorize(http))

    response = drive.files().list(
        q="title = '{}' and trashed = false".format(folder_name)).execute()

    if len(response.get('items')) > 0:
        return response.get('items')[0].get('id')

    return create_drive_folder(credentials, folder_name)


def new_spread_sheets(service, title, sheet_title, columns, rows):
    spread_sheet_details = {
        "properties":  {
            "title": title
        },
        'sheets': [
            {
                u'properties':
                    {
                        u'title': sheet_title,

                        u'gridProperties':
                        {
                            u'columnCount': columns,
                            u'rowCount': rows
                        }

                    }
            }
        ]
    }

    return service.spreadsheets().create(body=spread_sheet_details).execute()


def get_spread_sheet(service, spread_sheet_id):
    return service.spreadsheets().get(spreadsheetId=spread_sheet_id).execute()


def get_spread_sheet_url(spread_sheet_id):
    return SHEETS_BASE_URL % spread_sheet_id


def prepare_row(data, fields):
    return [encode_if_str(data, f, True) for f in fields]


def set_spread_sheet_data(service, spread_sheet_id, data, section, index):
    payload = {
            "majorDimension": "ROWS",
            "values": data,
    }
    sheet_range = "{}!A{}".format(section, index)
    results = service.spreadsheets()\
        .values()\
        .update(spreadsheetId=spread_sheet_id, body=payload, range=sheet_range,
                valueInputOption="USER_ENTERED").execute()

    return results


class GoogleSheetsExportBuilder(ExportBuilder):
    google_credentials = None
    service = None
    spread_sheet_details = None

    def __init__(self, xform, google_credentials, config={}):
        self.spreadsheet_title = \
            config.get('spreadsheet_title', xform.id_string)
        self.google_credentials = google_credentials
        self.service = create_service(google_credentials)
        self.set_survey(xform.survey)

    def export(self, path, data, username, xform=None, filter_query=None):
        section_name, headers = self._get_headers()
        columns = len(headers)
        rows = len(data) + 1 # include headers

        self.spread_sheet_details = \
            new_spread_sheets(self.service, self.spreadsheet_title,
                              section_name, columns, rows)

        self._insert_data(data, headers)

        self.url = get_spread_sheet_url(
            self.spread_sheet_details.get('spreadsheetId')
        )

    def _get_headers(self):
        """Writes headers for each section."""
        for section in self.sections:
            section_name = section['name']
            headers = [element['title'] for element in
                       section['elements']] + self.EXTRA_FIELDS

        return section_name, headers

    def _insert_data(self, data, headers, row_index=1):
        """Writes data rows for each section."""
        indices = {}
        survey_name = self.survey.name
        finalized_rows = list()
        finalized_rows.append(headers)
        for index, d in enumerate(data, 1):
            joined_export = dict_to_joined_export(
                d, index, indices, survey_name, self.survey, d)
            output = ExportBuilder.decode_mongo_encoded_section_names(
                joined_export)
            # attach meta fields (index, parent_index, parent_table)
            # output has keys for every section
            if survey_name not in output:
                output[survey_name] = {}
            output[survey_name][INDEX] = index
            output[survey_name][PARENT_INDEX] = -1
            for section in self.sections:
                # get data for this section and write to xls
                section_name = section['name']
                fields = [element['xpath'] for element in
                          section['elements']] + self.EXTRA_FIELDS

                # section might not exist within the output, e.g. data was
                # not provided for said repeat - write test to check this
                row = output.get(section_name, None)
                if type(row) == dict:
                    finalized_rows.append(
                        prepare_row(self.pre_process_row(row, section),
                                    fields))
                elif type(row) == list:
                    for child_row in row:
                        finalized_rows.append(
                            prepare_row(
                                self.pre_process_row(child_row, section),
                                fields))

        spread_sheet_id = self.spread_sheet_details.get('spreadsheetId')
        return set_spread_sheet_data(self.service, spread_sheet_id,
                                     finalized_rows, section_name, row_index)
