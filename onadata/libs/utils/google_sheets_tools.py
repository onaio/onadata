import httplib2

from apiclient import discovery
from oauth2client.contrib.django_orm import Storage

from django.conf import settings

from onadata.apps.main.models import TokenStorageModel
from onadata.libs.utils.export_tools import (
    ExportBuilder,
    dict_to_joined_export,
    encode_if_str
)
from onadata.libs.utils.common_tags import INDEX, PARENT_INDEX

DISCOVERY_URL = "https://sheets.googleapis.com/$discovery/rest?version=v4"
SHEETS_BASE_URL = 'https://docs.google.com/spreadsheet/ccc?key=%s&hl'
GOOGLE_SHEET_UPLOAD_BATCH = \
    getattr(settings, 'GOOGLE_SHEET_UPLOAD_BATCH', 1000)


def create_service(credentials):
    """
    Create google service which will interact with google api.
    :param credentials:
    :return: Authenticated google service
    """
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('sheets', 'v4', http=http,
                              discoveryServiceUrl=DISCOVERY_URL)
    return service


def create_google_sheet(user, title, xform=None):
    """
    Loads user oauth credential and creates a google sheet with the given
    title.
    :param user:
    :param title:
    :param xform:
    :return: google sheet id
    """
    storage = Storage(TokenStorageModel, 'id', user, 'credential')
    google_credentials = storage.get()

    service = create_service(google_credentials)

    if xform:
        section_name = xform.survey.name
    else:
        section_name = 'data'
    spread_sheet_details = new_spread_sheets(service, title,
                                             sheet_title=section_name)

    return spread_sheet_details.get('spreadsheetId')


def create_drive_folder(credentials, title="onadata"):
    """
    Create a folder in google drive.
    :param credentials:
    :param title: defaults to onadata
    :return: None
    """
    http = httplib2.Http()
    drive = discovery.build("drive", "v3", http=credentials.authorize(http))

    file_metadata = {
        'name': title,
        'mimeType': 'application/vnd.google-apps.folder'
    }

    drive.files().create(body=file_metadata, fields='id').execute()


def get_sheets_folder_id(credentials, folder_name="onadata"):
    """
    Return google drive folder unique id
    :param credentials:
    :param folder_name:
    :return:
    """
    http = httplib2.Http()
    drive = discovery.build("drive", "v3", http=credentials.authorize(http))

    response = drive.files().list(
        q="title = '{}' and trashed = false".format(folder_name)).execute()

    if len(response.get('items')) > 0:
        return response.get('items')[0].get('id')

    return create_drive_folder(credentials, folder_name)


def new_spread_sheets(service, title, sheet_title=None, columns=26, rows=1):
    """
    Creates a new google sheet witj one sheet
    :param service: Authenticated service
    :param title: s
    :param sheet_title:
    :param columns: default to 26
    :param rows: default to 1
    :return:
    """
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
    """
    Retrieve google sheet detail
    :param service: Authenticated service
    :param spread_sheet_id:
    :return: dict with google sheet details
    """
    return service.spreadsheets().get(spreadsheetId=spread_sheet_id).execute()


def get_spread_sheet_title(service, spread_sheet_id):
    """
    Returns the current google sheet title
    :param service:
    :param spread_sheet_id:
    :return:
    """
    google_sheet_details = get_spread_sheet(service, spread_sheet_id)

    return google_sheet_details.get('properties').get('title')


def get_spread_sheet_rows(service, spread_sheet_details, row_index=None):
    """
    Retrieve sheet data
    :param service:
    :param spread_sheet_details:
    :param row_index:
    :return:
    spread_sheet_details ->

    {
        u'properties':
            {
                u'autoRecalc': u'ON_CHANGE',
                u'defaultFormat':
                {
                    u'backgroundColor':
                    {
                        u'blue': 1, u'green': 1, u'red': 1
                    },
                    u'padding':
                    {
                        u'bottom': 2, u'left': 3, u'right': 3, u'top': 2
                    },
                    u'textFormat':
                    {
                        u'bold': False,
                        u'fontFamily': u'arial,sans,sans-serif',
                        u'fontSize': 10, u'foregroundColor': {},
                        u'italic': False, u'strikethrough': False,
                        u'underline': False
                    },
                    u'verticalAlignment': u'BOTTOM',
                    u'wrapStrategy': u'OVERFLOW_CELL'
                },
                u'locale': u'en_US',
                u'timeZone': u'Asia/Baghdad',
                u'title': u'weka-sync'
            },
            u'sheets':
                [
                    {
                        u'properties':
                            {
                                u'gridProperties':
                                    {
                                        u'columnCount': 41,
                                        u'rowCount': 11
                                    },
                                u'index': 0,
                                u'sheetId': 1836938579,
                                u'sheetType': u'GRID',
                                u'title': u'tom'
                            }
                    }
                ],
        u'spreadsheetId': u'16-58Zf5gDfuKwWFywtMOnJuVN2PTUELjd4Q3yTWAwMA'
    }
    """

    spread_sheet_id = spread_sheet_details.get('spreadsheetId')
    sheet_detail = spread_sheet_details.get('sheets')[0]
    grid_properties = sheet_detail.get('properties').get('gridProperties')
    rows = grid_properties.get('rowCount')
    columns = grid_properties.get('columnCount')

    if row_index:
        sheet_range = 'A{}:{}{}'.format(row_index, colnum_string(columns),
                                        row_index)
    else:
        sheet_range = 'A{}:{}{}'.format(1, colnum_string(columns), rows)

    return service.spreadsheets().values()\
        .get(spreadsheetId=spread_sheet_id, range=sheet_range)\
        .execute()


def get_spread_sheet_column(service, spread_sheet_details, column_index=None):
    spread_sheet_id = spread_sheet_details.get('spreadsheetId')
    sheet_detail = spread_sheet_details.get('sheets')[0]
    grid_properties = sheet_detail.get('properties').get('gridProperties')
    rows = grid_properties.get('rowCount')

    column_alpha = colnum_string(column_index)

    sheet_range = '{}{}:{}{}'.format(column_alpha, 1, column_alpha, rows)

    return service.spreadsheets().values() \
        .get(spreadsheetId=spread_sheet_id, range=sheet_range,
             majorDimension="COLUMNS").execute()


def get_spread_sheet_url(spread_sheet_id):
    """
    Generate google sheet url from the spread sheet id
    :param spread_sheet_id:
    :return:
    """
    return SHEETS_BASE_URL % spread_sheet_id


def prepare_row(data, fields):
    """
    creates array of data
    :param data:
    :param fields:
    :return:
    """
    return [encode_if_str(data, f, True) for f in fields]


def set_spread_sheet_data(service, spread_sheet_id, data, section, index):
    """
    Uploads data to google spread sheet
    :param service:
    :param spread_sheet_id:
    :param data:
    :param section:
    :param index:
    :return:
    """
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


def add_row_or_column(service, spread_sheet_id, sheet_id, columns=0, rows=1):
    """
    Extends the google sheets according to params provided
    :param service:
    :param spread_sheet_id:
    :param sheet_id:
    :param columns:
    :param rows:
    :return:
    """
    requests = list()

    if columns:
        requests.append({
          "appendDimension": {
            "sheetId": sheet_id,
            "dimension": "COLUMNS",
            "length": columns
          }
        })

    if rows:
        requests.append({
            "appendDimension": {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "length": rows
            }
        })

    payload = {
      "requests": requests
    }

    return service.spreadsheets()\
        .batchUpdate(spreadsheetId=spread_sheet_id, body=payload).execute()


def delete_row_or_column(service, spread_sheet_id, sheet_id, start_index,
                         end_index, dimension="ROWS"):
    """
    Deletes row or column
    :param service:
    :param spread_sheet_id:
    :param sheet_id:
    :param start_index:
    :param end_index:
    :param dimension:
    :return:
    """
    requests = list()

    requests.append({
        "deleteDimension": {
            "range": {
              "sheetId": sheet_id,
              "dimension": dimension,
              "startIndex": start_index,
              "endIndex": end_index
            }
          }
        })
    payload = {
      "requests": requests
    }

    return service.spreadsheets()\
        .batchUpdate(spreadsheetId=spread_sheet_id, body=payload).execute()


def colnum_string(n):
    """
    Generates excel alpha-numeric label given a column index
    E.g 27 -> AA
    :param n:
    :return:
    """
    div = n
    alpha_numeric = ""
    while div > 0:
        module = (div - 1) % 26
        alpha_numeric = chr(65 + module) + alpha_numeric
        div = int((div - module) / 26)
    return alpha_numeric


def search_rows(service, spread_sheet_id, column, value):
    spread_sheet_details = get_spread_sheet(service, spread_sheet_id)
    headers_details = get_spread_sheet_rows(service, spread_sheet_details,
                                            row_index=1)

    headers = headers_details.get("values")[0]
    header_index = headers.index(column) + 1

    data_column = get_spread_sheet_column(service, spread_sheet_details,
                                          column_index=header_index)
    data = data_column.get("values")[0]

    row_index = data.index(str(value)) + 1

    return row_index


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

    def export(self, data):
        section_name, headers = self._get_headers()
        columns = len(headers)
        rows = len(data) + 1  # include headers

        self.spread_sheet_details = \
            new_spread_sheets(self.service, self.spreadsheet_title,
                              section_name, columns, rows)
        spread_sheet_id = self.spread_sheet_details.get('spreadsheetId')

        self._add_headers(headers, spread_sheet_id, section_name)
        self._insert_data(data)

        self.url = get_spread_sheet_url(spread_sheet_id)

        return self.url

    def _get_headers(self):
        """Writes headers for each section."""
        for section in self.sections:
            section_name = section['name']
            headers = [element['title'] for element in
                       section['elements']] + self.EXTRA_FIELDS

        return section_name, headers

    def _add_headers(self, headers, spread_sheet_id, section_name):
        finalized_rows = list()
        finalized_rows.append(headers)

        return set_spread_sheet_data(self.service, spread_sheet_id,
                                     finalized_rows, section_name, 1)

    def _insert_data(self, data, row_index=2):
        """Writes data rows for each section."""
        indices = {}
        survey_name = self.survey.name
        finalized_rows = list()
        batch_size = GOOGLE_SHEET_UPLOAD_BATCH
        processed_data = 0
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

                if processed_data > batch_size:
                    spread_sheet_id = \
                        self.spread_sheet_details.get('spreadsheetId')
                    set_spread_sheet_data(self.service, spread_sheet_id,
                                          finalized_rows, section_name,
                                          row_index)
                    finalized_rows = []
                    row_index += processed_data + 1
                    processed_data = 0
                else:
                    processed_data += 1

        if finalized_rows:
            spread_sheet_id = self.spread_sheet_details.get('spreadsheetId')
            set_spread_sheet_data(self.service, spread_sheet_id,
                                  finalized_rows, section_name, row_index)

    def live_update(self, data, spreadsheet_id, delete=False, update=False,
                    append=False):
        section_name, headers = self._get_headers()
        columns = len(headers)
        rows = len(data) + 1  # include headers

        self.spread_sheet_details = \
            get_spread_sheet(self.service, spreadsheet_id)
        sheet_id = self.spread_sheet_details.get('properties').get('sheetId')
        spreadsheet_id = self.spread_sheet_details.get('spreadsheetId')

        if delete:
            start_index = search_rows(self.service, spreadsheet_id, '_id',
                                      data)
            return delete_row_or_column(self.service, spreadsheet_id, sheet_id,
                                        start_index, start_index+1)

        sheet_details = self.spread_sheet_details.get('sheets')[0]
        current_rows = sheet_details.get('properties').get('gridProperties') \
            .get('rowCount')

        # extend sheet if necessary
        self._extend_spread_sheet(sheet_details, spreadsheet_id,
                                  columns, rows, append)

        if append:
            start_index = current_rows + 1
        elif update:

            data_id = data[0].get('_id')
            start_index = search_rows(self.service, spreadsheet_id, '_id',
                                      data_id)

            data = data[0]
        else:
            start_index = 2

        self._add_headers(headers, spreadsheet_id, section_name)
        self._insert_data(data, row_index=start_index)

        self.url = get_spread_sheet_url(spreadsheet_id)

    def _extend_spread_sheet(self, sheet_details, spreadsheet_id, columns,
                             rows, append):
        current_columns = sheet_details.get('properties') \
            .get('gridProperties').get('columnCount')
        current_rows = sheet_details.get('properties').get('gridProperties') \
            .get('rowCount')
        sheet_id = sheet_details.get('properties').get('sheetId')

        columns_to_add = rows_to_add = 0
        if columns > current_columns:
            columns_to_add = columns - current_columns

        if rows > current_rows:
            rows_to_add = rows - current_rows

        if append:
            rows_to_add = rows if current_rows == 0 else rows - 1

        if columns_to_add or rows_to_add:
            add_row_or_column(self.service, spreadsheet_id, sheet_id,
                              columns=columns_to_add, rows=rows_to_add)
