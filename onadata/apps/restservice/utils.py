from oauth2client.contrib.django_orm import Storage

from onadata.apps.main.models import TokenStorageModel
from onadata.apps.restservice.models import RestService


def call_service(submission_instance):
    # lookup service
    services = RestService.objects.filter(
        xform_id=submission_instance.xform_id)
    # call service send with url and data parameters
    for sv in services:
        # TODO: Queue service
        try:
            service = sv.get_service_definition()()
            service.send(sv.service_url, submission_instance)
        except:
            # TODO: Handle gracefully | requeue/resend
            pass


def retrieve_user_google_credentials(user_pk):
    return Storage(TokenStorageModel, 'id', user_pk, 'credential').get()


def initialize_google_sheet_builder(xform, google_credentials,
                                    sheet_title=None):
    from onadata.libs.utils.google_sheets import SheetsExportBuilder

    if not sheet_title:
        sheet_title = xform.id_string
    config = {
        "spreadsheet_title": sheet_title,
        "flatten_repeated_fields": False
    }
    return SheetsExportBuilder(xform, google_credentials, config)
