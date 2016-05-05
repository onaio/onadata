from celery import task

from django.contrib.auth.models import User

from oauth2client.contrib.django_orm import Storage

from onadata.apps.main.models import TokenStorageModel
from onadata.apps.logger.import_tools import django_file
from onadata.libs.utils.logger_tools import create_instance
from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.models import MetaData
from onadata.libs.utils.common_tags import USER_ID, GOOGLE_SHEET_ID


@task(ignore_result=True)
def import_instance_async(username, xform_path, photos, osm_files, status):
    """
    This callback is passed an instance of a XFormInstanceFS.
    See xform_fs.py for more info.
    """
    with django_file(xform_path, field_name="xml_file",
                     content_type="text/xml") as xml_file:
        images = [django_file(jpg, field_name="image",
                  content_type="image/jpeg") for jpg in photos]
        images += [
            django_file(osm, field_name='image',
                        content_type='text/xml')
            for osm in osm_files
        ]
        try:
            create_instance(username, xml_file, images, status)
        except:
            pass

        for i in images:
            i.close()


@task()
def sync_delete_googlesheets(instance_pk, xform_pk):
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
    data = instance_pk

    google_sheets = SheetsExportBuilder(xform, google_credentials, config)
    google_sheets.live_update(path, data, xform, spreadsheet_id=spreadsheet_id,
                              delete=True)
