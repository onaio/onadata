from celery import task

from onadata.apps.logger.import_tools import django_file
from onadata.libs.utils.logger_tools import create_instance


@task
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
        # TODO: if an instance has been submitted make sure all the
        # files are in the database.
        # there shouldn't be any instances with a submitted status in the
        # import.
        instance = create_instance(username, xml_file, images, status)

        for i in images:
            i.close()

        if instance:
            return 1
        else:
            return 0
