from django.contrib.auth.models import User
from oauth2client.contrib.django_orm import Storage

from onadata.apps.restservice.RestServiceInterface import RestServiceInterface
from onadata.apps.main.models import MetaData
from onadata.libs.utils.google_sheets import SheetsExportBuilder
from onadata.apps.main.models import TokenStorageModel
from onadata.libs.utils.common_tags import GSHEET_TITLE, USER_ID


class ServiceDefinition(RestServiceInterface):
    id = u'googlesheets'
    verbose_name = u'Google Sheet Export'

    def send(self, url, submission_instance):
        spreadsheet_details = MetaData.get_gsheet_details(
            submission_instance.xform)
        config = {
            "spreadsheet_title": spreadsheet_details.get(GSHEET_TITLE),
            "flatten_repeated_fields": False
        }
        user_id = spreadsheet_details.get(USER_ID)
        user = User.objects.get(pk=user_id)
        storage = Storage(TokenStorageModel, 'id', user, 'credential')

        google_credentials = storage.get()
        xform = submission_instance.xform
        path = None
        data = [submission_instance.json]
        google_sheets = SheetsExportBuilder(xform, google_credentials, config)
        google_sheets.live_update(path, data, xform)
