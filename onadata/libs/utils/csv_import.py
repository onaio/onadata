import unicodecsv as ucsv
import uuid
from cStringIO import StringIO
from onadata.libs.utils.logger_tools import dict2xform, create_instance
from onadata.apps.logger.models import Instance


class CSVImportException(Exception):
    pass


def csv_submit_rollback(uuids):
    Instance.objects.filter(uuid__in=uuids).delete()


def dict2xmlsubmission(xml_submission, uuid):
    return dict2xform(xml_submission, uuid, u'submission')


def submit_csv(username, csv_data):

    if isinstance(csv_data, (str, unicode)):
        csv_data = StringIO(csv_data)
    elif not isinstance(csv_data, file):
        raise TypeError(u'Invalid param type for `csv_data`. '
                        'Expected file, String or Unicode but '
                        'got {} instead.'.format(type(csv_data).__name__))

    csv_reader = ucsv.DictReader(csv_data)
    rollback_uuids = []
    for row in csv_reader:
        # fetch submission uuid before purging row metadata
        row_uuid = row.get('_uuid', uuid.uuid4())
        rollback_uuids.append(row_uuid)

        for key in row.keys():  # seems faster than a comprehension
            # remove metadata (keys starting with '_')
            if key.startswith('_'):
                del row[key]
            # process nested data e.g x[formhub/uuid] => x[formhub][uuid]
            if r'/' in key:
                p, c = key.split('/')
                row[p] = { c : row[key] }
                del row[key]

        xml_file = StringIO(dict2xmlsubmission(row, row_uuid))

        try:
            create_instance(username, xml_file, [], None, None)
        except:
            # there has to be a more elegant way to roll back
            # the following is a stop-gap
            csv_submit_rollback(rollback_uuids)
            raise
