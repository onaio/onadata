from datetime import timedelta

from celery import task
# from celery.task.schedules import crontab
from celery.decorators import periodic_task
from celery.utils.log import get_task_logger

from oauth2client.contrib.django_orm import Storage

from django.contrib.auth.models import User

from onadata.apps.main.models import TokenStorageModel
from onadata.apps.restservice.utils import call_service
from onadata.apps.restservice.models import RestService
from onadata.apps.logger.models import (
    Instance,
    XForm
)
from onadata.apps.main.models import MetaData
from onadata.libs.utils.common_tags import USER_ID, GOOGLE_SHEET_ID

from onadata.apps.logger.models.xform import XForm


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
        xform_id=instance.xform_id, name='googlesheets'
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
    from onadata.libs.utils.google_sheets import SheetsExportBuilder
    from onadata.apps.viewer.models.parsed_instance import query_data
    config = {
        "spreadsheet_title": spreadsheet_title,
        "flatten_repeated_fields": False
    }
    xform = XForm.objects.get(pk=xform_pk)
    path = None
    data = query_data(xform)

    google_sheets = SheetsExportBuilder(xform, google_credentials, config)
    google_sheets.live_update(path, data, xform, spreadsheet_id)


@task()
def sync_update_googlesheets(instance_pk, xform_pk):
    from onadata.libs.utils.google_sheets import SheetsExportBuilder

    xform = XForm.objects.get(pk=xform_pk)
    spreadsheet_details = MetaData.get_gsheet_details(xform)

    config = {
        "spreadsheet_title": xform.id_string,
        "flatten_repeated_fields": False
    }
    user_id = spreadsheet_details.get(USER_ID)
    spreadsheet_id = spreadsheet_details.get(GOOGLE_SHEET_ID)
    user = User.objects.get(pk=user_id)
    storage = Storage(TokenStorageModel, 'id', user, 'credential')

    google_credentials = storage.get()

    path = None
    submission_instance = Instance.objects.get(pk=instance_pk)
    data = [submission_instance.json]

    google_sheets = SheetsExportBuilder(xform, google_credentials, config)
    google_sheets.live_update(path, data, xform, spreadsheet_id=spreadsheet_id,
                              update=True)




