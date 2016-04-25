from onadata.apps.restservice.RestServiceInterface import RestServiceInterface
from onadata.apps.main.models import MetaData
from onadata.libs.utils.google_sheets import SheetsExportBuilder
from onadata.libs.utils.common_tags import (
    GSHEET_TITLE,
    # UPDATE_OR_DELETE_GSHEET_DATA
)


class ServiceDefinition(RestServiceInterface):
    id = u'gsheets'
    verbose_name = u'Gsheet export'

    def send(self, url, submission_instance):
        spreadsheet_title = MetaData.get_gsheet_details(
            submission_instance.xform)
        config = {
            "spreadsheet_title": spreadsheet_title.get(GSHEET_TITLE),
            "flatten_repeated_fields": True
        }
        google_credentials = None
        xform = submission_instance.xform
        path = None
        username = None
        filter_query = None
        data = None

        google_sheets = SheetsExportBuilder(xform, google_credentials, config)
        google_sheets.export(path, data, username, xform, filter_query)
