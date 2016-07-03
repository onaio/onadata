from requests.exceptions import ConnectionError

from celery import task

from onadata.apps.restservice.utils import call_service,\
    retrieve_user_google_credentials, initialize_google_sheet_builder
from onadata.apps.restservice.models import RestService
from onadata.apps.logger.models import (
    Instance,
    XForm
)
from onadata.apps.main.models import MetaData
from onadata.libs.utils.common_tags import USER_ID, GOOGLE_SHEET_ID,\
    GOOGLE_SHEET


@task()
def call_service_async(instance_pk):
    # load the parsed instance
    from onadata.apps.logger.models.instance import Instance

    try:
        instance = Instance.objects.get(pk=instance_pk)
    except Instance.DoesNotExist:
        # if the instance has already been removed we do not send it to the
        # service
        pass
    else:
        call_service(instance)


@task(bind=True)
def call_google_sheet_service(self, instance_pk):
    # lookup service
    instance = Instance.objects.get(pk=instance_pk)
    sv = RestService.objects.filter(
        xform_id=instance.xform_id, name=GOOGLE_SHEET
    ).first()

    # call service send with url and data parameters
    if sv:
        try:
            service = sv.get_service_definition()()
            service.send(sv.service_url, instance)
        except ConnectionError, exc:
            self.retry(exc=exc, countdown=60)


@task(bind=True)
def initial_google_sheet_export(self, xform_pk, google_credentials,
                                spreadsheet_title, spreadsheet_id):
    from onadata.apps.viewer.models.parsed_instance import query_data

    try:
        xform = XForm.objects.get(pk=xform_pk)
        data = query_data(xform)
        google_sheets = initialize_google_sheet_builder(xform,
                                                        google_credentials,
                                                        spreadsheet_title)

        google_sheets.live_update(data, spreadsheet_id)
    except ConnectionError, exc:
        self.retry(exc=exc, countdown=60)


@task(bind=True)
def sync_update_google_sheets(self, instance_pk, xform_pk):
    xform = XForm.objects.get(pk=xform_pk)
    spreadsheet_details = MetaData.get_google_sheet_details(xform.pk)

    user_id = spreadsheet_details.get(USER_ID)
    spreadsheet_id = spreadsheet_details.get(GOOGLE_SHEET_ID)
    google_credentials = retrieve_user_google_credentials(user_id)

    submission_instance = Instance.objects.get(pk=instance_pk)
    data = [submission_instance.json]

    google_sheets = initialize_google_sheet_builder(xform, google_credentials)

    try:
        google_sheets.live_update(data, spreadsheet_id, update=True)
    except ConnectionError, exc:
        self.retry(exc=exc, countdown=60)


@task(bind=True)
def sync_delete_google_sheets(self, instance_pk, xform_pk):
    xform = XForm.objects.get(pk=xform_pk)
    spreadsheet_details = MetaData.get_google_sheet_details(xform.pk)

    user_id = spreadsheet_details.get(USER_ID)
    spreadsheet_id = spreadsheet_details.get(GOOGLE_SHEET_ID)
    google_credentials = retrieve_user_google_credentials(user_id)
    data = instance_pk

    google_sheets = initialize_google_sheet_builder(xform, google_credentials)
    try:
        google_sheets.live_update(data, spreadsheet_id, delete=True)
    except ConnectionError, exc:
        self.retry(exc=exc, countdown=60)
