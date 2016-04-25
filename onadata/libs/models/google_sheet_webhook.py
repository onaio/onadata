from onadata.apps.restservice.models import RestService
from onadata.apps.main.models.meta_data import MetaData


class GoogleSheetService(object):

    def __init__(self, xform=None, service_url=None, name=None,
                 google_sheet_title=None, send_existing_data=True,
                 sync_updates=True, pk=None):
        self.pk = pk
        self.xform = xform
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

        gsheets_metadata = 'GSHEET_TITLE {} | '\
            'UPDATE_OR_DELETE_GSHEET_DATA {}'\
            .format(self.google_sheet_title, self.sync_updates)

        MetaData.set_gsheet_details(self.xform, gsheets_metadata)

        self.pk = rs.pk

    def retrieve(self):
        gsheet_details = MetaData.get_gsheet_details(self.xform)

        self.google_sheet_title = gsheet_details.get('GSHEET_TITLE')
        self.sync_updates = gsheet_details.get('UPDATE_OR_DELETE_GSHEET_DATA')
        self.send_existing_data = False
