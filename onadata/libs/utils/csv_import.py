# -*- coding: utf-8 -*-
"""
CSV data import module.
"""
import functools
import json
import logging
import sys
import uuid
from builtins import str as text
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from io import BytesIO

import unicodecsv as ucsv
import xlrd
from celery import current_task, task
from celery.backends.amqp import BacklogLimitExceeded
from celery.result import AsyncResult
from dateutil.parser import parse
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.translation import ugettext as _
from future.utils import iteritems
from multidb.pinning import use_master

from onadata.apps.logger.models import Instance, XForm
from onadata.libs.utils.async_status import (FAILED, async_status,
                                             celery_state_to_status)
from onadata.libs.utils.common_tags import (MULTIPLE_SELECT_TYPE, EXCEL_TRUE,
                                            XLS_DATE_FIELDS,
                                            XLS_DATETIME_FIELDS)
from onadata.libs.utils.common_tools import report_exception
from onadata.libs.utils.dict_tools import csv_dict_to_nested_dict
from onadata.libs.utils.logger_tools import (OpenRosaResponse, dict2xml,
                                             safe_create_instance)

DEFAULT_UPDATE_BATCH = 100
PROGRESS_BATCH_UPDATE = getattr(settings, 'EXPORT_TASK_PROGRESS_UPDATE_BATCH',
                                DEFAULT_UPDATE_BATCH)
IGNORED_COLUMNS = ['formhub/uuid', 'meta/instanceID']


def get_submission_meta_dict(xform, instance_id):
    """Generates metadata for our submission

    Checks if `instance_id` belongs to an existing submission.
    If it does, it's considered an edit and its uuid gets deprecated.
    In either case, a new one is generated and assigned.

    :param onadata.apps.logger.models.XForm xform: The submission's XForm.
    :param string instance_id: The submission/instance `uuid`.

    :return: The metadata dict
    :rtype:  dict
    """
    uuid_arg = instance_id or 'uuid:{}'.format(uuid.uuid4())
    meta = {'instanceID': uuid_arg}

    update = 0

    if instance_id and xform.instances.filter(
            uuid=instance_id.replace('uuid:', '')).count() > 0:
        uuid_arg = 'uuid:{}'.format(uuid.uuid4())
        meta.update({
            'instanceID': uuid_arg,
            'deprecatedID': instance_id
        })
        update += 1
    return [meta, update]


def dict2xmlsubmission(submission_dict, xform, instance_id, submission_date):
    """Creates and xml submission from an appropriate dict (& other data)

    :param dict submission_dict: A dict containing form submission data.
    :param onadata.apps.logger.models.XForm xfrom: The submission's XForm.
    :param string instance_id: The submission/instance `uuid`.
    :param string submission_date: An isoformatted datetime string.

    :return: An xml submission string
    :rtype: string
    """

    return (u'<?xml version="1.0" ?>'
            '<{0} id="{1}" instanceID="uuid:{2}" submissionDate="{3}">{4}'
            '</{0}>'.format(
                json.loads(xform.json).get('name', xform.id_string),
                xform.id_string, instance_id, submission_date,
                dict2xml(submission_dict).replace('\n', ''))).encode('utf-8')


def dict_merge(a, b):
    """ Returns a merger of two dicts a and b

    credits: https://www.xormedia.com/recursively-merge-dictionaries-in-python

    :param dict a: The "Part A" dict
    :param dict b: The "Part B" dict
    :return: The merger
    :rtype: dict
    """
    if not isinstance(b, dict):
        return b
    result = deepcopy(a)
    for (k, v) in iteritems(b):
        if k in result and isinstance(result[k], dict):
            result[k] = dict_merge(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result


def dict_pathkeys_to_nested_dicts(dictionary):
    """ Turns a flat dict to a nested dict

    Takes a dict with pathkeys or "slash-namespaced" keys and inflates
    them into nested dictionaries i.e:-
    `d['/path/key/123']` -> `d['path']['key']['123']`

    :param dict dictionary: A dict with one or more "slash-namespaced" keys
    :return: A nested dict
    :rtype: dict
    """
    data = dictionary.copy()
    for key in list(data):
        if r'/' in key:
            data = dict_merge(
                functools.reduce(lambda v, k: {k: v},
                                 (key.split('/') + [data.pop(key)])[::-1]),
                data)

    return data


@task()
def submit_csv_async(username, xform_id, file_path, overwrite=False):
    """Imports CSV data to an existing xform asynchrounously."""
    xform = XForm.objects.get(pk=xform_id)

    with default_storage.open(file_path) as csv_file:
        return submit_csv(username, xform, csv_file, overwrite)


def failed_import(rollback_uuids, xform, exception, status_message):
    """ Report a failed import.
    :param rollback_uuids: The rollback UUIDs
    :param xform: The XForm that failed to import to
    :param exception: The exception object
    :return: The async_status result
    """
    Instance.objects.filter(uuid__in=rollback_uuids, xform=xform).delete()
    report_exception(
        'CSV Import Failed : %d - %s - %s' % (xform.pk, xform.id_string,
                                              xform.title), exception,
        sys.exc_info())
    return async_status(FAILED, status_message)


@use_master
def submit_csv(username, xform, csv_file, overwrite=False):
    """Imports CSV data to an existing form

    Takes a csv formatted file or string containing rows of submission/instance
    and converts those to xml submissions and finally submits them by calling
    :py:func:`onadata.libs.utils.logger_tools.safe_create_instance`

    :param str username: the subission user
    :param onadata.apps.logger.models.XForm xfrom: The submission's XForm.
    :param (str or file): A CSV formatted file with submission rows.
    :return: If sucessful, a dict with import summary else dict with error str.
    :rtype: Dict
    """
    # TODO: Split this section ↓ into separate validate_csv function
    # Validate csv_file is utf-8 encoded or unicode
    if isinstance(csv_file, str):
        csv_file = BytesIO(csv_file)
    elif csv_file is None or not hasattr(csv_file, 'read'):
        return async_status(
            FAILED,
            (u'Invalid param type for csv_file`.'
             'Expected utf-8 encoded file or unicode'
             ' string got {} instead'.format(type(csv_file).__name__)))

    # Change stream position to start of file
    csv_file.seek(0)

    csv_reader = ucsv.DictReader(csv_file, encoding='utf-8-sig')
    csv_headers = csv_reader.fieldnames

    # Make sure CSV headers have no spaces
    if any(' ' in header for header in csv_headers):
        return async_status(
            FAILED,
            u'CSV file fieldnames should not contain spaces'
        )

    # Get headers from stored data dictionary
    xform_headers = xform.get_headers()

    # Identify any missing columns or additional columns between
    # XForm and Imported CSV
    missing_col = list(set(xform_headers).difference(csv_headers))
    additional_col = list(set(csv_headers).difference(xform_headers))

    # Remove all metadata columns
    missing_col = [
        col for col in missing_col
        if not col.startswith('_') and col not in IGNORED_COLUMNS
        ]
    # remove all metadata inside groups
    missing_col = [col for col in missing_col if '/_' not in col]

    # ignore if is multiple select question
    for col in csv_headers:
        # this col is a multiple select question
        survey_element = xform.get_survey_element(col)
        if survey_element and \
                survey_element.get('type') == MULTIPLE_SELECT_TYPE:
            # remove from the missing and additional list
            missing_col = [x for x in missing_col if not x.startswith(col)]
            additional_col.remove(col)

    # remove headers for repeats that might be missing from csv
    missing_col = sorted([m for m in missing_col if m.find('[') == -1])

    if missing_col:
        return async_status(
            FAILED, u"Sorry uploaded file does not match the form. "
            u"The file is missing the column(s): "
            u"{0}.".format(', '.join(missing_col)))

    # Include additional repeats
    additional_col = [a for a in additional_col if a.find('[') == -1]

    x_json = json.loads(xform.json)

    def get_columns_by_type(type_list):
        """Returns a column that match types passed within
        the field_list

        :param type_list: A list containing strings that represent
                                  XLS field types
        """
        return [
            dt.get('name') for dt in x_json.get('children')
            if dt.get('type') in type_list
        ]

    # Retrieve the columns we should validate values for
    # Currently validating date, datetime, integer and decimal columns
    columns = {
        'date': (get_columns_by_type(XLS_DATE_FIELDS), parse),
        'datetime': (get_columns_by_type(XLS_DATETIME_FIELDS), parse),
        'integer': (get_columns_by_type(['integer']), int),
        'decimal': (get_columns_by_type(['decimal']), float)
    }

    valid_data = True
    row_count = 0
    validated_rows = []
    errors = {}

    for row in csv_reader:
        row_count += 1

        # Remove additional columns
        for index in additional_col:
            del row[index]

        # Remove 'n/a' values and '' values for xls
        row = {k: v for (k, v) in row.items() if v != 'n/a' and v != ''}

        # Validate that row data
        row, error = validate_row(row, columns)

        if error:
            valid_data = False
            errors[row_count] = error

        if valid_data:
            location_data = {}

            for key in list(row):
                # Collect row location data into separate location_data dict
                if key.endswith(('.latitude', '.longitude', '.altitude',
                                 '.precision')):
                    location_key, location_prop = key.rsplit(u'.', 1)
                    location_data.setdefault(location_key, {}).update({
                        location_prop:
                        row.get(key, '0')
                    })

            # TODO: Maybe do this in the if conditional above ?
            # collect all location K-V pairs into single geopoint field(s)
            # in location_data dict
            for location_key in list(location_data):
                location_data.update({
                    location_key:
                    (u'%(latitude)s %(longitude)s '
                        '%(altitude)s %(precision)s') % defaultdict(
                        lambda: '', location_data.get(location_key))
                })

            row = csv_dict_to_nested_dict(row)
            location_data = csv_dict_to_nested_dict(location_data)
            row = dict_merge(row, location_data)

            validated_rows.append(row)

    # TODO: Split this section ↑ into separate validate_csv function

    if not valid_data:
        return async_status(
            FAILED,
            u'Invalid CSV data imported: {}'.format(
                errors
            )
        )

    if overwrite:
        xform.instances.filter(deleted_at__isnull=True)\
            .update(deleted_at=timezone.now(),
                    deleted_by=User.objects.get(username=username))

    rollback_uuids = []
    ona_uuid = {'formhub': {'uuid': xform.uuid}}
    submission_time = datetime.utcnow().isoformat()
    additions = duplicates = inserts = 0

    for row in validated_rows:
        row_uuid = row.get('meta/instanceID') or 'uuid:{}'.format(
                row.get('_uuid')) if row.get('_uuid') else None
        submitted_by = row.get('_submitted_by')
        submission_date = row.get('_submission_time', submission_time)

        for key in list(row):
            # remove metadata (keys starting with '_')
            if key.startswith('_'):
                del row[key]

        # Inject our forms uuid into the submission
        row.update(ona_uuid)

        old_meta = row.get('meta', {})
        new_meta, update = get_submission_meta_dict(xform, row_uuid)
        inserts += update
        old_meta.update(new_meta)
        row.update({'meta': old_meta})

        row_uuid = row.get('meta').get('instanceID')
        rollback_uuids.append(row_uuid.replace('uuid:', ''))

        xml_file = BytesIO(
            dict2xmlsubmission(row, xform, row_uuid, submission_date))

        try:
            error, instance = safe_create_instance(
                username, xml_file, [], xform.uuid, None)
        except ValueError as e:
            error = e

        if error:
            if not (isinstance(error, OpenRosaResponse)
                    and error.status_code == 202):
                Instance.objects.filter(
                    uuid__in=rollback_uuids, xform=xform).delete()
                return async_status(FAILED, text(error))
            else:
                duplicates += 1
        else:
            additions += 1

            if additions % PROGRESS_BATCH_UPDATE == 0:
                try:
                    current_task.update_state(
                        state='PROGRESS',
                        meta={
                            'progress': additions,
                            'total': row_count,
                            'info': additional_col
                        })
                except Exception:
                    logging.exception(
                        _(u'Could not update state of '
                            'import CSV batch process.'))
                finally:
                    xform.submission_count(True)

            users = User.objects.filter(
                username=submitted_by) if submitted_by else []
            if users:
                instance.user = users[0]
                instance.save()

    return {
        "additions": additions - inserts,
        "duplicates": duplicates,
        u"updates": inserts,
        u"info": u"Additional column(s) excluded from the upload: '{0}'."
        .format(', '.join(list(additional_col)))}


def get_async_csv_submission_status(job_uuid):
    """ Gets CSV Submision progress or result
    Can be used to pol long running submissions
    :param str job_uuid: The submission job uuid returned by _submit_csv.delay
    :return: Dict with import progress info (insertions & total)
    :rtype: Dict
    """
    if not job_uuid:
        return async_status(FAILED, u'Empty job uuid')

    job = AsyncResult(job_uuid)
    try:
        # result = (job.result or job.state)
        if job.state not in ['SUCCESS', 'FAILURE']:
            response = async_status(celery_state_to_status(job.state))
            if isinstance(job.info, dict):
                response.update(job.info)

            return response

        if job.state == 'FAILURE':
            return async_status(
                celery_state_to_status(job.state), text(job.result))

    except BacklogLimitExceeded:
        return async_status(celery_state_to_status('PENDING'))

    return job.get()


def submission_xls_to_csv(xls_file):
    """Convert a submission xls file to submissions csv file

    :param xls_file: submissions xls file
    :return: csv_file
    """
    xls_file.seek(0)
    xls_file_content = xls_file.read()
    xl_workbook = xlrd.open_workbook(file_contents=xls_file_content)
    first_sheet = xl_workbook.sheet_by_index(0)

    csv_file = BytesIO()
    csv_writer = ucsv.writer(csv_file)

    date_columns = []
    boolean_columns = []

    # write the header
    csv_writer.writerow(first_sheet.row_values(0))

    # check for any dates or boolean in the first row of data
    for index in range(first_sheet.ncols):
        if first_sheet.cell_type(1, index) == xlrd.XL_CELL_DATE:
            date_columns.append(index)
        elif first_sheet.cell_type(1, index) == xlrd.XL_CELL_BOOLEAN:
            boolean_columns.append(index)

    for row in range(1, first_sheet.nrows):
        row_values = first_sheet.row_values(row)

        # convert excel dates(floats) to datetime
        for date_column in date_columns:
            try:
                row_values[date_column] = xlrd.xldate_as_datetime(
                    row_values[date_column],
                    xl_workbook.datemode).isoformat()
            except (ValueError, TypeError):
                row_values[date_column] = first_sheet.cell_value(
                    row, date_column)

        # convert excel boolean to true/false
        for boolean_column in boolean_columns:
            row_values[boolean_column] = bool(
                row_values[boolean_column] == EXCEL_TRUE)

        csv_writer.writerow(row_values)

    return csv_file


def validate_row(row, columns):
    """ """
    def validate_column_data(column, constraint_check):
        """ """
        invalid_data = []
        validated_data = {}

        for key in column:
            value = row.get(key, '')

            if value:
                try:
                    value = constraint_check(value)
                except ValueError:
                    invalid_data.append(value)
                else:
                    validated_data[key] = value

        if invalid_data:
            return (False, invalid_data)
        else:
            return (True, validated_data)

    # Check data doesn't infringe on XForm data constraints
    errors = []
    for datatype in columns:
        column, constraint_check = columns.get(datatype)
        valid, data = validate_column_data(column, constraint_check)

        if valid:
            if datatype == 'date':
                for key in data:
                    value = datetime.strftime(data.get(key), '%Y-%m-%d')
                    data.update({key: value})

            elif datatype == 'datetime':
                for key in data:
                    value = datetime.strftime(
                        data.get(key), '%Y-%m-%dT%H:%M:%S.%f%z')
                    data.update({key: value})

            row.update(data)
        else:
            errors.append('Unknown {} format(s): {}'.format(
                        datatype, ', '.join(data)))

    return (row, errors)
