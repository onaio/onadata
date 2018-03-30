# encoding=utf-8
import os
import shutil
import tempfile
import zipfile
from builtins import open

from celery import task
from django.core.files.uploadedfile import InMemoryUploadedFile

from onadata.apps.logger.xform_fs import XFormInstanceFS
from onadata.libs.utils.logger_tools import create_instance

# odk
# ├── forms
# │   ├── Agriculture_2011_03_18.xml
# │   ├── Education_2011_03_18.xml
# │   ├── Health_2011_03_18.xml
# │   ├── LGA_2011_03_18.xml
# │   ├── Registration_2011_03_18.xml
# │   └── Water_2011_03_18.xml
# ├── instances
# │   ├── Education_2011_03_18_2011-03-23_11-07-36
# │   │   ├── 1300878537573.jpg
# │   │   └── Education_2011_03_18_2011-03-23_11-07-36.xml
# │   ├── Registration_2011_03_18_2011-03-21_19-33-34
# │   │   └── Registration_2011_03_18_2011-03-21_19-33-34.xml
# └── metadata
#     └── data


def django_file(path, field_name, content_type):
    # adapted from here:
    # http://groups.google.com/group/django-users/browse_thread/thread/
    # 834f988876ff3c45/
    f = open(path, 'rb')
    return InMemoryUploadedFile(
        file=f,
        field_name=field_name,
        name=f.name,
        content_type=content_type,
        size=os.path.getsize(path),
        charset=None
    )


def import_instance(username, xform_path, photos, osm_files, status,
                    raise_exception):
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
            instance = create_instance(username, xml_file, images, status)
        except Exception as e:
            if raise_exception:
                raise e

        for i in images:
            i.close()

        if instance:
            return 1
        else:
            return 0


@task(ignore_result=True)
def import_instance_async(username, xform_path, photos, osm_files, status):
    import_instance(username, xform_path, photos, osm_files, status, False)


def iterate_through_instances(dirpath, callback, user=None, status='zip',
                              is_async=False):
    total_file_count = 0
    success_count = 0
    errors = []

    for directory, subdirs, subfiles in os.walk(dirpath):
        for filename in subfiles:
            filepath = os.path.join(directory, filename)
            if XFormInstanceFS.is_valid_instance(filepath):
                xfxs = XFormInstanceFS(filepath)
                if is_async and user is not None:
                    callback.apply_async((
                        user.username, xfxs.path, xfxs.photos, xfxs.osm, status
                    ), queue='instances')
                    success_count += 1
                else:
                    try:
                        success_count += callback(xfxs)
                    except Exception as e:
                        errors.append("%s => %s" % (xfxs.filename, str(e)))
                    del(xfxs)
                total_file_count += 1

    return (total_file_count, success_count, errors)


def import_instances_from_zip(zipfile_path, user, status="zip"):
    try:
        temp_directory = tempfile.mkdtemp()
        zf = zipfile.ZipFile(zipfile_path)

        zf.extractall(temp_directory)
    except zipfile.BadZipfile as e:
        errors = [u"%s" % e]
        return 0, 0, errors
    else:
        return import_instances_from_path(temp_directory, user, status)
    finally:
        shutil.rmtree(temp_directory)


def import_instances_from_path(path, user, status="zip", is_async=False):
    def callback(xform_fs):
        """
        This callback is passed an instance of a XFormInstanceFS.
        See xform_fs.py for more info.
        """
        import_instance(user.username,
                        xform_fs.path,
                        xform_fs.photos,
                        xform_fs.osm,
                        status,
                        True)

    if is_async:
        total_count, success_count, errors = iterate_through_instances(
            path,
            import_instance_async,
            user=user,
            status=status,
            is_async=is_async
        )
    else:
        total_count, success_count, errors = iterate_through_instances(
            path, callback
        )

    return (total_count, success_count, errors)
