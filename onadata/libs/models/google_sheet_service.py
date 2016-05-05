from oauth2client.contrib.django_orm import Storage

from onadata.apps.main.models import TokenStorageModel
from onadata.apps.restservice.models import RestService
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.restservice.tasks import initial_google_sheet_export
from onadata.libs.utils.google_sheets import get_google_sheet_id
from onadata.libs.utils.common_tags import GOOGLE_SHEET_ID,\
    UPDATE_OR_DELETE_GOOGLE_SHEET_DATA, USER_ID, GOOGLE_SHEET_TITLE


class GoogleSheetService(object):

    def __init__(self, user=None, xform=None, service_url=None, name=None,
                 google_sheet_title=None, send_existing_data=True,
                 sync_updates=True, pk=None):
        self.pk = pk
        self.xform = xform
        self.user = user
        self.name = name
        self.service_url = service_url
        self.google_sheet_title = google_sheet_title
        self.send_existing_data = send_existing_data
        self.sync_updates = sync_updates

    def save(self, **kwargs):

        rs = RestService() if not self.pk else \
            RestService.objects.get(pk=self.pk)

        rs.name = self.name
        rs.service_url = self.service_url
        rs.xform = self.xform
        rs.save()

        spreadsheet_id = \
            get_google_sheet_id(self.user, self.google_sheet_title)

        google_sheets_metadata = \
            '{} {} | {} {}| {} {} | {} {}'.format(
                GOOGLE_SHEET_ID, spreadsheet_id,
                UPDATE_OR_DELETE_GOOGLE_SHEET_DATA, self.sync_updates,
                USER_ID, self.user.pk,
                GOOGLE_SHEET_TITLE, self.google_sheet_title
            )

        MetaData.set_google_sheet_details(self.xform, google_sheets_metadata)

        self.pk = rs.pk

        if self.send_existing_data and self.xform.instances.count() > 0:
            storage = Storage(TokenStorageModel, 'id', self.user,
                              'credential')
            google_credentials = storage.get()
            initial_google_sheet_export.apply_async(
                args=[self.xform.pk, google_credentials,
                      self.google_sheet_title, spreadsheet_id],
                countdown=1
            )

    def retrieve(self):
        google_sheet_details = MetaData.get_google_sheet_details(self.xform)

        self.google_sheet_title = google_sheet_details.get(GOOGLE_SHEET_ID)
        self.sync_updates = \
            google_sheet_details.get(UPDATE_OR_DELETE_GOOGLE_SHEET_DATA)
        self.send_existing_data = False
