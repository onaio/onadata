import unicodecsv as ucsv
import uuid
import json

import cStringIO
from datetime import datetime
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

                # process nested data e.g x[formhub/uuid] => x[formhub][uuid]
                if r'/' in key:
                    p, c = key.split('/')
                    row[p] = {c: row[key]}
                    del row[key]

                if key.endswith(('.latitude', '.longitude',
                                '.altitude', '.precision')):
                    location_data.setdefault(
                        key.split('.')[0], {}).update(
                            {key.split('.')[-1]: row.get(key, '0')})

            for key in location_data.keys():
                row.update({key: (u'{latitude} {longitude} '
                                  '{altitude} {precision}'
                                  '').format(**location_data.get(key))})

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
