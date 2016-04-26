from celery import task
from onadata.apps.restservice.utils import call_service

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

@task()
def initial_google_sheet_export(xform_pk, google_credentials,
                                spreadsheet_title):
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
    google_sheets.live_update(path, data, xform)