import json
import logging
import sys
import unicodecsv as ucsv
import uuid
from builtins import str as text
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from functools import reduce
from future.utils import iteritems
from io import BytesIO
from past.builtins import basestring

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.utils.translation import ugettext as _

from celery import current_task, task
from celery.backends.amqp import BacklogLimitExceeded
from celery.result import AsyncResult

from onadata.apps.logger.models import Instance
from onadata.libs.utils.async_status import (FAILED, async_status,
                                             celery_state_to_status)
from onadata.libs.utils.common_tags import MULTIPLE_SELECT_TYPE
from onadata.libs.utils.common_tools import report_exception
from onadata.libs.utils.dict_tools import csv_dict_to_nested_dict
from onadata.libs.utils.logger_tools import dict2xml, safe_create_instance

DEFAULT_UPDATE_BATCH = 100
PROGRESS_BATCH_UPDATE = getattr(settings, 'EXPORT_TASK_PROGRESS_UPDATE_BATCH',
                                DEFAULT_UPDATE_BATCH)


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
    uuid_arg = 'uuid:{}'.format(uuid.uuid4())
    meta = {'instanceID': uuid_arg}

    update = 0

    if xform.instances.filter(uuid=instance_id).count() > 0:
        uuid_arg = 'uuid:{}'.format(uuid.uuid4())
        meta.update({
            'instanceID': uuid_arg,
            'deprecatedID': 'uuid:{}'.format(instance_id)
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
    d = dictionary.copy()
    for key in list(d):
        if r'/' in key:
            d = dict_merge(
                reduce(lambda v, k: {k: v},
                       (key.split('/') + [d.pop(key)])[::-1]), d)
    return d


@task()
def submit_csv_async(username, xform, file_path):
    with default_storage.open(file_path) as csv_file:
        return submit_csv(username, xform, csv_file)


def failed_import(rollback_uuids, xform, exception, status_message):
    """ Report a failed import.
    :param rollback_uuids: The rollback UUIDs
    :param xform: The XForm that failed to import to
    :param exception: The exception object
    :return: The async_status result
    """
    Instance.objects.filter(uuid__in=rollback_uuids, xform=xform).delete()
    report_exception('CSV Import Failed : %d - %s - %s' %
                     (xform.pk, xform.id_string, xform.title),
                     exception,
                     sys.exc_info())
    return async_status(FAILED, status_message)


def submit_csv(username, xform, csv_file):
    """ Imports CSV data to an existing form

    Takes a csv formatted file or string containing rows of submission/instance
    and converts those to xml submissions and finally submits them by calling
    :py:func:`onadata.libs.utils.logger_tools.safe_create_instance`

    :param str username: the subission user
    :param onadata.apps.logger.models.XForm xfrom: The submission's XForm.
    :param (str or file): A CSV formatted file with submission rows.
    :return: If sucessful, a dict with import summary else dict with error str.
    :rtype: Dict
    """
    if isinstance(csv_file, str):
        csv_file = BytesIO(csv_file)
    elif csv_file is None or not hasattr(csv_file, 'read'):
        return async_status(FAILED, (u'Invalid param type for `csv_file`. '
                                     'Expected utf-8 encoded file or unicode'
                                     ' string got {} instead.'
                                     .format(type(csv_file).__name__)))

    num_rows = sum(1 for row in csv_file) - 1
    csv_file.seek(0)

    csv_reader = ucsv.DictReader(csv_file, encoding='utf-8-sig')
    csv_header = csv_reader.fieldnames

    # check for spaces in headers
    if any(' ' in header for header in csv_header):
        return async_status(FAILED,
                            u'CSV file fieldnames should not contain spaces')

    # Get the data dictionary
    xform_header = xform.get_headers()

    missing_col = set(xform_header).difference(csv_header)
    addition_col = set(csv_header).difference(xform_header)

    # change to list
    missing_col = list(missing_col)
    addition_col = list(addition_col)
    # remove all metadata columns
    missing = [col for col in missing_col if not col.startswith("_")]

    # remove all meta/instanceid columns

    while 'meta/instanceID' in missing:
        missing.remove('meta/instanceID')

    # remove all metadata inside groups
    missing = [col for col in missing if not ("/_" in col)]

    # ignore if is multiple select question
    for col in csv_header:
        # this col is a multiple select question
        survey_element = xform.get_survey_element(col)
        if survey_element and \
                survey_element.get('type') == MULTIPLE_SELECT_TYPE:
            # remove from the missing and additional list
            missing = [x for x in missing if not x.startswith(col)]

            addition_col.remove(col)

    # remove headers for repeats that might be missing from csv
    missing = sorted([m for m in missing if m.find('[') == -1])

    # Include additional repeats
    addition_col = [a for a in addition_col if a.find('[') == -1]

    if missing:
        return async_status(FAILED,
                            u"Sorry uploaded file does not match the form. "
                            u"The file is missing the column(s): "
                            u"{0}.".format(', '.join(missing)))

    rollback_uuids = []
    submission_time = datetime.utcnow().isoformat()
    ona_uuid = {'formhub': {'uuid': xform.uuid}}
    error = None
    additions = inserts = 0
    try:
        for row in csv_reader:
            # remove the additional columns
            for index in addition_col:
                del row[index]

            # fetch submission uuid before purging row metadata
            row_uuid = row.get('_uuid')
            submitted_by = row.get('_submitted_by')
            submission_date = row.get('_submission_time', submission_time)

            location_data = {}
            for key in list(row):  # seems faster than a comprehension
                # remove metadata (keys starting with '_')
                if key.startswith('_'):
                    del row[key]

                # Collect row location data into separate location_data dict
                if key.endswith(('.latitude', '.longitude', '.altitude',
                                 '.precision')):
                    location_key, location_prop = key.rsplit(u'.', 1)
                    location_data.setdefault(location_key, {}).update({
                        location_prop:
                        row.get(key, '0')
                    })
                # remove 'n/a' values
                if not key.startswith('_') and row[key] == 'n/a':
                    del row[key]

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

            # inject our form's uuid into the submission
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
                error, instance = safe_create_instance(username, xml_file, [],
                                                       xform.uuid, None)
            except ValueError as e:
                error = e

            if error:
                Instance.objects.filter(
                    uuid__in=rollback_uuids, xform=xform).delete()
                return async_status(FAILED, text(error))
            else:
                additions += 1
                if additions % PROGRESS_BATCH_UPDATE == 0:
                    try:
                        current_task.update_state(
                            state='PROGRESS',
                            meta={
                                'progress': additions,
                                'total': num_rows,
                                'info': addition_col
                            })
                    except Exception:
                        logging.exception(_(u'Could not update state of '
                                            'import CSV batch process.'))
                    finally:
                        xform.submission_count(True)

                users = User.objects.filter(
                    username=submitted_by) if submitted_by else []
                if users:
                    instance.user = users[0]
                    instance.save()

    except UnicodeDecodeError as e:
        return failed_import(
            rollback_uuids, xform, e, u'CSV file must be utf-8 encoded')
    except Exception as e:
        return failed_import(rollback_uuids, xform, e, text(e))
    finally:
        xform.submission_count(True)

    return {
        u"additions":
        additions - inserts,
        u"updates":
        inserts,
        u"info":
        u"Additional column(s) excluded from the upload: '{0}'."
        .format(', '.join(list(addition_col)))
    }


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
        result = (job.result or job.state)

        if isinstance(result, (Exception)):
            return async_status(
                celery_state_to_status(job.state), text(job.result))

        if isinstance(result, basestring):
            return async_status(celery_state_to_status(job.state))

    except BacklogLimitExceeded:
        return async_status(celery_state_to_status('PENDING'))

    return result
