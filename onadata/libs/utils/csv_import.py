import cStringIO
import json
import unicodecsv as ucsv
import uuid

from celery import task
from celery import current_task
from celery.result import AsyncResult
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from django.conf import settings
from django.contrib.auth.models import User
from onadata.libs.utils.logger_tools import dict2xml, safe_create_instance
from onadata.apps.logger.models import Instance


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
        meta.update({'instanceID': uuid_arg,
                     'deprecatedID': 'uuid:{}'.format(instance_id)})
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
            '<{0} id="{1}" instanceID="uuid:{2}" submissionDate="{3}" '
            'xmlns="http://opendatakit.org/submissions">{4}'
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
    for k, v in b.iteritems():
        if k in result and isinstance(result[k], dict):
            result[k] = dict_merge(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result


def dict_pathkeys_to_nested_dicts(d):
    """ Turns a flat dict to a nested dict

    Takes a dict with pathkeys or "slash-namespaced" keys and inflates
    them into nested dictionaries i.e:-
    `d['/path/key/123']` -> `d['path']['key']['123']`

    :param dict dictionary: A dict with one or more "slash-namespaced" keys
    :return: A nested dict
    :rtype: dict
    """
    for key in d.keys():
        if r'/' in key:
            d = dict_merge(reduce(lambda v, k: {k: v},
                           (key.split('/')+[d.pop(key)])[::-1]), d)
    return d


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
    if isinstance(csv_file, unicode):
        csv_file = cStringIO.StringIO(csv_file)
    elif csv_file is None or not hasattr(csv_file, 'read'):
        return {'error': (u'Invalid param type for `csv_file`. '
                          'Expected utf-8 encoded file or unicode string '
                          'got {} instead.'.format(type(csv_file).__name__))}

    csv_file.seek(0)
    num_rows = sum(1 for row in csv_file) - 1
    submition_task = _submit_csv.delay(username, xform, csv_file, num_rows)
    if num_rows < settings.CSV_ROW_IMPORT_ASYNC_THRESHOLD:
        return submition_task.wait()

    return {'task_uuid': submition_task.id}


@task
def _submit_csv(username, xform, csv_file, num_rows=0):
    """ Does the actuall CSV submission task """
    csv_file.seek(0)

    csv_reader = ucsv.DictReader(csv_file)
    # check for spaces in headers
    if any(' ' in header for header in csv_reader.fieldnames):
        return {'error': u'CSV file fieldnames should not contain spaces'}

    rollback_uuids = []
    submission_time = datetime.utcnow().isoformat()
    ona_uuid = {'formhub': {'uuid': xform.uuid}}
    error = None
    additions = inserts = 0
    try:
        for row in csv_reader:
            # fetch submission uuid before purging row metadata
            row_uuid = row.get('_uuid')
            submitted_by = row.get('_submitted_by')
            submission_date = row.get('_submission_time', submission_time)

            location_data = {}
            for key in row.keys():  # seems faster than a comprehension
                # remove metadata (keys starting with '_')
                if key.startswith('_'):
                    del row[key]

                # Collect row location data into separate location_data dict
                if key.endswith(('.latitude', '.longitude',
                                '.altitude', '.precision')):
                    location_key, location_prop = key.rsplit(u'.', 1)
                    location_data.setdefault(location_key, {}).update(
                        {location_prop: row.get(key, '0')})

            # collect all location K-V pairs into single geopoint field(s)
            # in location_data dict
            for location_key in location_data.keys():
                location_data.update(
                    {location_key:
                     (u'%(latitude)s %(longitude)s '
                      '%(altitude)s %(precision)s') % defaultdict(
                          lambda: '', location_data.get(location_key))})

            row = dict_pathkeys_to_nested_dicts(row)
            location_data = dict_pathkeys_to_nested_dicts(location_data)

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

            xml_file = cStringIO.StringIO(
                dict2xmlsubmission(row, xform, row_uuid, submission_date))

            try:
                error, instance = safe_create_instance(username, xml_file, [],
                                                       xform.uuid, None)
            except ValueError as e:
                error = e

            if error:
                Instance.objects.filter(uuid__in=rollback_uuids,
                                        xform=xform).delete()
                return {'error': str(error)}
            else:
                additions += 1
                current_task.update_state(state='PROGRESS',
                                          meta={'progress': additions,
                                                'total': num_rows})
                users = User.objects.filter(
                    username=submitted_by) if submitted_by else []
                if users:
                    instance.user = users[0]
                    instance.save()

    except UnicodeDecodeError:
        Instance.objects.filter(uuid__in=rollback_uuids,
                                xform=xform).delete()
        return {'error': u'CSV file must be utf-8 encoded'}
    except Exception as e:
        Instance.objects.filter(uuid__in=rollback_uuids,
                                xform=xform).delete()
        return {'error': str(e)}

    return {'additions': additions - inserts, 'updates': inserts}


def get_async_csv_submission_status(job_uuid):
    """ Gets CSV Submision progress

    Can be used to pol long running submissions
    :param str job_uuid: The submission job uuid returned by _submit_csv.delay
    :return: Dict with import progress info (insertions & total)
    :rtype: Dict
    """
    job = AsyncResult(job_uuid)
    return (job.result or job.state)
