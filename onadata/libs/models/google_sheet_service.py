from oauth2client.contrib.django_orm import Storage
from django.conf import settings
from django.db import IntegrityError
from django.utils.translation import ugettext as _
from rest_framework import serializers

from onadata.apps.main.models import TokenStorageModel
from onadata.apps.restservice.models import RestService
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.restservice.tasks import initial_google_sheet_export
from onadata.libs.utils.google_sheets_tools import get_spread_sheet_url
from onadata.libs.utils.common_tags import GOOGLE_SHEET_ID,\
    UPDATE_OR_DELETE_GOOGLE_SHEET_DATA, USER_ID, GOOGLE_SHEET_TITLE, \
    SYNC_EXISTING_DATA
from onadata.libs.utils.google_sheets_tools import create_google_sheet


class GoogleSheetService(object):

    def __init__(self, user=None, xform=None, service_url=None, name=None,
                 google_sheet_title=None, send_existing_data=True,
                 sync_updates=True, google_sheet_url=None, pk=None):
        self.pk = pk
        self.xform = xform
        self.user = user
        self.name = name
        self.service_url = service_url
        self.google_sheet_title = google_sheet_title
        self.send_existing_data = send_existing_data
        self.sync_updates = sync_updates
        self.google_sheet_url = google_sheet_url
        self.date_created = None
        self.date_modified = None

    def save(self, **kwargs):

        rs = RestService() if not self.pk else \
            RestService.objects.get(pk=self.pk)

        rs.name = self.name
        rs.service_url = self.service_url
        rs.xform = self.xform
        try:
            rs.save()
        except IntegrityError as e:
            if str(e).startswith("duplicate key value violates unique "
                                 "constraint"):
                msg = _(u"The service already created for this form.")
            else:
                msg = _(str(e))

            raise serializers.ValidationError(msg)

        self.date_created = rs.date_created
        self.date_modified = rs.date_modified

        # Check if its an update and retrieve the google sheet id
        if kwargs.get('update'):
            google_details = MetaData.get_google_sheet_details(self.xform.pk)
            spreadsheet_id = google_details.get(GOOGLE_SHEET_ID)
        else:
            spreadsheet_id = create_google_sheet(self.user,
                                                 self.google_sheet_title,
                                                 self.xform)

        google_sheets_metadata = \
            '{} {} | {} {}| {} {} | {} {} | {} {}'.format(
                GOOGLE_SHEET_ID, spreadsheet_id,
                UPDATE_OR_DELETE_GOOGLE_SHEET_DATA, self.sync_updates,
                USER_ID, self.user.pk,
                GOOGLE_SHEET_TITLE, self.google_sheet_title,
                SYNC_EXISTING_DATA, self.send_existing_data
            )

        MetaData.set_google_sheet_details(self.xform, google_sheets_metadata)

        self.pk = rs.pk
        self.google_sheet_url = get_spread_sheet_url(spreadsheet_id)

        if self.send_existing_data and self.xform.instances.count() > 0:
            storage = Storage(TokenStorageModel, 'id', self.user,
                              'credential')
            google_credentials = storage.get()
            retry_policy = {
                'max_retries': getattr(settings, 'DEFAULT_CELERY_MAX_RETIRES',
                                       3),
                'interval_start':
                    getattr(settings, 'DEFAULT_CELERY_INTERVAL_START', 1),
                'interval_step': getattr(settings,
                                         'DEFAULT_CELERY_INTERVAL_STEP',
                                         0.5),
                'interval_max': getattr(settings,
                                        'DEFAULT_CELERY_INTERVAL_MAX', 0.5)
            }
            initial_google_sheet_export.apply_async(
                args=[self.xform.pk, google_credentials,
                      self.google_sheet_title, spreadsheet_id],
                countdown=10, retry_policy=retry_policy
            )

    def retrieve(self):
        google_sheet_details = MetaData.get_google_sheet_details(self.xform.pk)

        self.google_sheet_title = google_sheet_details.get(GOOGLE_SHEET_TITLE)
        self.sync_updates = \
            google_sheet_details.get(UPDATE_OR_DELETE_GOOGLE_SHEET_DATA)
        self.send_existing_data = google_sheet_details.get(SYNC_EXISTING_DATA,
                                                           True)
        self.user = google_sheet_details.get(USER_ID)
        self.google_sheet_url = get_spread_sheet_url(
            google_sheet_details.get(GOOGLE_SHEET_ID))
