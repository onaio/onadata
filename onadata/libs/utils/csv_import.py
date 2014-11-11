import unicodecsv as ucsv
import uuid
import json

from cStringIO import StringIO
from datetime import datetime
from onadata.libs.utils.logger_tools import dict2xml, create_instance
from onadata.apps.logger.models import Instance


class CSVImportException(Exception):
    pass


def get_submission_meta_dict(xform, instance_id):
    uuid_arg = 'uuid:{}'.format(uuid.uuid4())
    meta = {'instanceID': uuid_arg}

    if len(xform.instances.filter(uuid=instance_id)) > 0:
        uuid_arg = 'uuid:{}'.format(uuid.uuid4())
        meta.update({'instanceID': uuid_arg,
                     'deprecatedID': 'uuid:{}'.format(instance_id)})
    return meta


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
        csv_data = StringIO(csv_data)
    elif not isinstance(csv_data, file):
        raise TypeError(u'Invalid param type for `csv_data`. '
                        'Expected file, String or Unicode but '
                        'got {} instead.'.format(type(csv_data).__name__))

    csv_reader = ucsv.DictReader(csv_data)
    rollback_uuids = []
    submission_time = datetime.utcnow().isoformat()
    ona_uuid = {'formhub': {'uuid': xform.uuid}}
    for row in csv_reader:
        # fetch submission uuid before purging row metadata
        row_uuid = row.get('_uuid')
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
        old_meta.update(get_submission_meta_dict(xform, row_uuid))
        row.update({'meta': old_meta})

        row_uuid = row.get('meta').get('instanceID')
        rollback_uuids.append(row_uuid.replace('uuid:', ''))

        xml_file = StringIO(dict2xmlsubmission(row, xform, row_uuid,
                                               submission_date))

        try:
            create_instance(username, xml_file, [],
                            u'submitted_via_web', xform.uuid)
        except:
            # there has to be a more elegant way to roll back
            # the following is a stop-gap
            Instance.objects.filter(uuid__in=rollback_uuids,
                                    xform=xform).delete()
            raise
