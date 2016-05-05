from datetime import timedelta

from celery import task
from celery.decorators import periodic_task
from celery.utils.log import get_task_logger

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


@periodic_task(
    # Execute every 12 hours i.e twice a day
    # run_every=(crontab(minute=0, hour='*/12')),
    run_every=timedelta(seconds=30),
    name="call_google_sheet_service ",
    ignore_result=True
)
def call_google_sheet_service(instance_pk):
    # lookup service
    instance = Instance.objects.get(pk=instance_pk)
    service = RestService.objects.filter(
        xform_id=instance.xform_id, name=GOOGLE_SHEET
    ).first()

    # call service send with url and data parameters
    try:
        service = service.get_service_definition()()
        service.send(service.service_url, instance)
        # TODO: check that the sent service is successful so that the instance
        # bucket can be updated
    except Exception:
        # TODO: Handle gracefully | requeue/resend
        pass


@task()
def initial_google_sheet_export(xform_pk, google_credentials,
                                spreadsheet_title, spreadsheet_id):
    from onadata.apps.viewer.models.parsed_instance import query_data

    xform = XForm.objects.get(pk=xform_pk)
    path = None
    data = query_data(xform)

    google_sheets = initialize_google_sheet_builder(xform, google_credentials,
                                                    spreadsheet_title)
    google_sheets.live_update(path, data, xform, spreadsheet_id)


@task()
def sync_delete_googlesheets(instance_pk, xform_pk):
    from onadata.libs.utils.google_sheets import SheetsExportBuilder

    xform = XForm.objects.get(pk=xform_pk)
    spreadsheet_details = MetaData.get_gsheet_details(xform)

    user_id = spreadsheet_details.get(USER_ID)
    spreadsheet_id = spreadsheet_details.get(GOOGLE_SHEET_ID)
    google_credentials = retrieve_user_google_credentials(user_id)

    path = None
    data = instance_pk

    google_sheets = initialize_google_sheet_builder(xform, google_credentials)
    google_sheets.live_update(path, data, xform, spreadsheet_id=spreadsheet_id,
                              delete=True)

@task()
def sync_update_google_sheets(instance_pk, xform_pk):
    xform = XForm.objects.get(pk=xform_pk)
    spreadsheet_details = MetaData.get_google_sheet_details(xform)

    user_id = spreadsheet_details.get(USER_ID)
    spreadsheet_id = spreadsheet_details.get(GOOGLE_SHEET_ID)
    google_credentials = retrieve_user_google_credentials(user_id)

    path = None
    submission_instance = Instance.objects.get(pk=instance_pk)
    data = [submission_instance.json]

    google_sheets = initialize_google_sheet_builder(xform, google_credentials)
    google_sheets.live_update(path, data, xform, spreadsheet_id=spreadsheet_id,
                              update=True)


@task()
def sync_delete_google_sheets(instance_pk, xform_pk):
    xform = XForm.objects.get(pk=xform_pk)
    spreadsheet_details = MetaData.get_google_sheet_details(xform)

    user_id = spreadsheet_details.get(USER_ID)
    spreadsheet_id = spreadsheet_details.get(GOOGLE_SHEET_ID)
    google_credentials = retrieve_user_google_credentials(user_id)

    path = None
    data = instance_pk

    google_sheets = initialize_google_sheet_builder(xform, google_credentials)
    google_sheets.live_update(path, data, xform, spreadsheet_id=spreadsheet_id,
                              delete=True)
