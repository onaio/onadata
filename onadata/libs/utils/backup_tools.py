# -*- coding: utf-8 -*-
"""
Backup utilities.
"""
import codecs
import errno
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from time import sleep

from onadata.apps.logger.import_tools import django_file
from onadata.apps.logger.models import Instance
from onadata.libs.utils.logger_tools import create_instance
from onadata.libs.utils.model_tools import queryset_iterator

DATE_FORMAT = "%Y-%m-%d-%H-%M-%S"


def _date_created_from_filename(filename):
    base_name, _ext = os.path.splitext(filename)
    parts = base_name.split("-")
    if len(parts) < 6:
        raise ValueError(
            "Inavlid filename - it must be in the form 'YYYY-MM-DD-HH-MM-SS[-i].xml'"
        )
    parts_dict = dict(zip(["year", "month", "day", "hour", "min", "sec"], parts))
    # pylint: disable=consider-using-f-string
    return datetime.strptime(
        "%(year)s-%(month)s-%(day)s-%(hour)s-%(min)s-%(sec)s" % parts_dict,
        DATE_FORMAT,
    )


# pylint: disable=too-many-locals
def create_zip_backup(zip_output_file, user, xform=None):
    """Create a ZIP file with a user's XForms and submissions."""
    # create a temp dir that we'll create our structure within and zip it
    # when we are done
    tmp_dir_path = tempfile.mkdtemp()

    instances_path = os.path.join(tmp_dir_path, "instances")

    # get the xls file from storage

    # for each submission in the database - create an xml file in this
    # form
    # /<id_string>/YYYY/MM/DD/YYYY-MM-DD-HH-MM-SS.xml
    queryset = Instance.objects.filter(xform__user=user)
    if xform:
        queryset = queryset.filter(xform=xform)

    num_instances = queryset.count()
    done = 0
    sys.stdout.write("Creating XML Instances\n")
    for instance in queryset_iterator(queryset, 100):
        # get submission time
        date_time_str = instance.date_created.strftime(DATE_FORMAT)
        date_parts = date_time_str.split("-")
        sub_dirs = os.path.join(*date_parts[:3])
        # create the directories
        full_path = os.path.join(instances_path, sub_dirs)
        if not os.path.exists(full_path):
            try:
                os.makedirs(full_path)
            except OSError as error:
                if error.errno != errno.EEXIST:
                    raise

        full_xml_path = os.path.join(full_path, date_time_str + ".xml")
        # check for duplicate file names
        file_index = 1
        while os.path.exists(full_xml_path):
            full_xml_path = os.path.join(full_path, f"{date_time_str}-{file_index}.xml")
            file_index += 1
        # create the instance xml
        with codecs.open(full_xml_path, "wb", "utf-8") as xml_file:
            xml_file.write(instance.xml)
        done += 1
        # pylint: disable=consider-using-f-string
        sys.stdout.write("\r%.2f %% done" % (float(done) / float(num_instances) * 100))
        sys.stdout.flush()
        sleep(0)

    # write zip file
    sys.stdout.write("\nWriting to ZIP archive.\n")
    with zipfile.ZipFile(
        zip_output_file, "w", zipfile.ZIP_DEFLATED, allowZip64=True
    ) as zip_file:
        done = 0
        for dir_path, _dir_names, file_names in os.walk(tmp_dir_path):
            for file_name in file_names:
                archive_path = dir_path.replace(tmp_dir_path + os.path.sep, "", 1)
                zip_file.write(
                    os.path.join(dir_path, file_name),
                    os.path.join(archive_path, file_name),
                )
                done += 1
                # pylint: disable=consider-using-f-string
                sys.stdout.write(
                    "\r%.2f %% done" % (float(done) / float(num_instances) * 100)
                )
                sys.stdout.flush()
                sleep(0)
    # removed dir tree
    shutil.rmtree(tmp_dir_path)
    sys.stdout.write(f"\nBackup saved to {zip_output_file}\n")


def restore_backup_from_zip(zip_file_path, username):
    """Restores XForms and submission instances from a ZIP backup file."""
    try:
        temp_directory = tempfile.mkdtemp()
        with zipfile.ZipFile(zip_file_path) as zip_file:
            zip_file.extractall(temp_directory)
    except zipfile.BadZipfile:
        sys.stderr.write("Bad zip archive.")
    else:
        return restore_backup_from_path(temp_directory, username)
    finally:
        shutil.rmtree(temp_directory)
    return None


def restore_backup_from_xml_file(xml_instance_path, username):
    """Creates submission instances in the DB from a submission XML file."""
    # check if its a valid xml instance
    file_name = os.path.basename(xml_instance_path)
    xml_file = django_file(
        xml_instance_path, field_name="xml_file", content_type="text/xml"
    )
    media_files = []
    try:
        date_created = _date_created_from_filename(file_name)
    except ValueError:
        sys.stderr.write(
            f"Couldn't determine date created from filename: '{file_name}'\n"
        )
        date_created = datetime.now()

    sys.stdout.write(f"Creating instance from '{file_name}'\n")
    try:
        create_instance(
            username, xml_file, media_files, date_created_override=date_created
        )
        return 1
    except Exception as error:  # pylint: disable=broad-except
        sys.stderr.write(
            f"Could not restore {file_name}, create instance said: {error}\n"
        )
        return 0


def restore_backup_from_path(dir_path, username):
    """
    Only restores xml submissions, media files are assumed to still be in
    storage and will be retrieved by the filename stored within the submission
    """
    num_instances = 0
    num_restored = 0
    for _dir_path, _dir_names, file_names in os.walk(dir_path):
        for file_name in file_names:
            # check if its a valid xml instance
            xml_instance_path = os.path.join(_dir_path, file_name)
            num_instances += 1
            num_restored += restore_backup_from_xml_file(xml_instance_path, username)
    return num_instances, num_restored
