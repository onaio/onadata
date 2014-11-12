import unicodecsv as ucsv
import uuid
import json

import cStringIO
from datetime import datetime
from django.contrib.auth.models import User
from onadata.libs.utils.logger_tools import dict2xml, safe_create_instance
from onadata.apps.logger.models import Instance


class CSVImportException(Exception):
    pass


def get_submission_meta_dict(xform, instance_id):
    """ generate metadata for our submission """
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

    return (u'<?xml version="1.0" ?>'
            '<{0} id="{1}" instanceID="uuid:{2}" submissionDate="{3}" '
            'xmlns="http://opendatakit.org/submissions">{4}'
            '</{0}>'.format(
                json.loads(xform.json).get('name', xform.id_string),
                xform.id_string, instance_id, submission_date,
                dict2xml(submission_dict).replace('\n', '')))


def submit_csv(username, xform, csv_data):

    if isinstance(csv_data, (str, unicode)):
        csv_data = cStringIO.StringIO(csv_data)
    elif csv_data.read is None:
        raise TypeError(u'Invalid param type for `csv_data`. '
                        'Expected file or String '
                        'got {} instead.'.format(type(csv_data).__name__))

    csv_reader = ucsv.DictReader(csv_data)
    rollback_uuids = []
    submission_time = datetime.utcnow().isoformat()
    ona_uuid = {'formhub': {'uuid': xform.uuid}}
    error = None
    additions = inserts = 0
    for row in csv_reader:
        # fetch submission uuid before purging row metadata
        row_uuid = row.get('_uuid')
        submitted_by = row.get('_submitted_by')
        submission_date = row.get('_submission_time', submission_time)

        for key in row.keys():  # seems faster than a comprehension
            # remove metadata (keys starting with '_')
            if key.startswith('_'):
                del row[key]
            # process nested data e.g x[formhub/uuid] => x[formhub][uuid]
            if r'/' in key:
                p, c = key.split('/')
                row[p] = {c: row[key]}
                del row[key]

        # inject our form's uuid into the submission
        row.update(ona_uuid)

        old_meta = row.get('meta', {})
        new_meta, update = get_submission_meta_dict(xform, row_uuid)
        inserts += update
        old_meta.update(new_meta)
        row.update({'meta': old_meta})

        row_uuid = row.get('meta').get('instanceID')
        rollback_uuids.append(row_uuid.replace('uuid:', ''))

        xml_file = cStringIO.StringIO(dict2xmlsubmission(row, xform, row_uuid,
                                      submission_date))

        try:
            error, instance = safe_create_instance(username, xml_file, [],
                                                   xform.uuid, None)
        except ValueError as e:
            error = e.message

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

    return {'additions': additions - inserts, 'updates': inserts}
