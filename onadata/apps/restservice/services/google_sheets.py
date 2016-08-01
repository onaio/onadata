
from onadata.apps.restservice.RestServiceInterface import RestServiceInterface
from onadata.apps.main.models import MetaData
from onadata.apps.restservice.utils import retrieve_user_google_credentials,\
    initialize_google_sheet_builder
from onadata.libs.utils.common_tags import GOOGLE_SHEET_ID, USER_ID


class ServiceDefinition(RestServiceInterface):
    id = u'google_sheets'
    verbose_name = u'Google Sheet Export'

    def send(self, url, submission_instance):
        spreadsheet_details = MetaData.get_google_sheet_details(
            submission_instance.xform.pk)
        xform = submission_instance.xform
        user_id = spreadsheet_details.get(USER_ID)

        google_credentials = retrieve_user_google_credentials(user_id)
        spreadsheet_id = spreadsheet_details.get(GOOGLE_SHEET_ID)
        data = [submission_instance.json]
        google_sheets = initialize_google_sheet_builder(xform,
                                                        google_credentials)
        google_sheets.live_update(data, spreadsheet_id)
