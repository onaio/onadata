# -*- coding: utf-8 -*-
"""
Import forms and submission utility functions.
"""
import os
import shutil
import tempfile
import zipfile
from contextlib import ExitStack

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http.response import Http404

from onadata.apps.logger.xform_fs import XFormInstanceFS
from onadata.celeryapp import app
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
    """Returns an InMemoryUploadedFile object of a given file at the ``path``."""
    # adapted from here:
    # http://groups.google.com/group/django-users/browse_thread/thread/
    # 834f988876ff3c45/
    # pylint: disable=consider-using-with
    a_file = open(path, "rb")
    return InMemoryUploadedFile(
        file=a_file,
        field_name=field_name,
        name=a_file.name,
        content_type=content_type,
        size=os.path.getsize(path),
        charset=None,
    )


# pylint: disable=too-many-arguments, too-many-positional-arguments
def import_instance(username, xform_path, photos, osm_files, status):
    """
    This callback is passed an instance of a XFormInstanceFS.
    See xform_fs.py for more info.
    """
    with ExitStack() as stack:
        submission_file = stack.enter_context(open(xform_path, "rb"))
        xml_file = stack.enter_context(
            InMemoryUploadedFile(
                submission_file,
                "xml_file",
                xform_path,
                "text/xml",
                os.path.getsize(xform_path),
                None,
            )
        )
        _media_files = [
            (stack.enter_context(open(path, "rb")), path, "image/jpeg")
            for path in photos
        ]
        _media_files += [
            (stack.enter_context(open(path, "rb")), path, "text/xml")
            for path in osm_files
        ]
        media_files = [
            stack.enter_context(
                InMemoryUploadedFile(
                    open_file,
                    "image",
                    path,
                    content_type,
                    os.path.getsize(path),
                    None,
                )
            )
            for open_file, path, content_type in _media_files
        ]
        instance = create_instance(username, xml_file, media_files, status)

        if instance:
            return 1
        return 0


@app.task(ignore_result=True)
def import_instance_async(username, xform_path, photos, osm_files, status):
    """An async alias to import_instance() function."""
    import_instance(username, xform_path, photos, osm_files, status)


def iterate_through_instances(
    dirpath, callback, user=None, status="zip", is_async=False
):
    """Iterate through all files and directories in the given ``dirpath``."""
    total_file_count = 0
    success_count = 0
    errors = []

    # pylint: disable=too-many-nested-blocks
    for directory, _subdirs, subfiles in os.walk(dirpath):
        for filename in subfiles:
            filepath = os.path.join(directory, filename)
            if XFormInstanceFS.is_valid_instance(filepath):
                xfxs = XFormInstanceFS(filepath)
                if is_async and user is not None:
                    callback.apply_async(
                        (user.username, xfxs.path, xfxs.photos, xfxs.osm, status),
                        queue="instances",
                    )
                    success_count += 1
                else:
                    try:
                        count = callback(xfxs)
                    except Http404:
                        pass
                    else:
                        if count:
                            success_count += count
                    del xfxs
                total_file_count += 1

    return (total_file_count, success_count, errors)


def import_instances_from_zip(zipfile_path, user, status="zip"):
    """Unzips a zip file and imports submission instances from it."""
    temp_directory = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(zipfile_path) as zip_file:
            zip_file.extractall(temp_directory)
    except zipfile.BadZipfile as error:
        errors = [f"{error}"]
        return 0, 0, errors
    else:
        return import_instances_from_path(temp_directory, user, status)
    finally:
        shutil.rmtree(temp_directory)


def import_instances_from_path(path, user, status="zip", is_async=False):
    """Process all submission instances in the given directory tree at ``path``."""

    def callback(xform_fs):
        """
        This callback is passed an instance of a XFormInstanceFS.
        See xform_fs.py for more info.
        """
        import_instance(
            user.username, xform_fs.path, xform_fs.photos, xform_fs.osm, status
        )

    if is_async:
        total_count, success_count, errors = iterate_through_instances(
            path, import_instance_async, user=user, status=status, is_async=is_async
        )
    else:
        total_count, success_count, errors = iterate_through_instances(path, callback)

    return (total_count, success_count, errors)
