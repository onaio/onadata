import unicodecsv as ucsv
import uuid

from cStringIO import StringIO
from datetime import datetime
from onadata.libs.utils.logger_tools import dict2xml, create_instance
from onadata.apps.logger.models import Instance


class CSVImportException(Exception):
    pass


def csv_submit_rollback(uuids):
    Instance.objects.filter(uuid__in=uuids).delete()


def dict2xmlsubmission(submission_dict, form_id, instance_id, submission_date):
    return (u'<?xml version="1.0" ?>'
            '<{0} id="{0}" instanceID="uuid:{1}" submissionDate="{2}" '
            'xmlns="http://opendatakit.org/submissions">{3}'
            '</{0}>'.format(form_id, instance_id, submission_date,
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
        row_uuid = row.get('_uuid', uuid.uuid4())
        submission_date = row.get('_submission_time', submission_time)
        rollback_uuids.append(row_uuid)

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

        xml_file = StringIO(dict2xmlsubmission(row, xform.id_string, row_uuid,
                                               submission_date))

        try:
            create_instance(username, xml_file, [],
                            u'submitted_via_web', xform.uuid)
        except:
            # there has to be a more elegant way to roll back
            # the following is a stop-gap
            csv_submit_rollback(rollback_uuids)
            raise
