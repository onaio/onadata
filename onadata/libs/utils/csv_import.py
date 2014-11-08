import unicodecsv as ucsv
import uuid
from cStringIO import StringIO
from onadata.apps.api.viewsets.xform_submission_api import dict_lists2strings
from onadata.libs.utils.logger_tools import dict2xml, safe_create_instance
from onadata.apps.logger.models import Instance


class CSVImportException(Exception):
    pass


def csv_submit_rollback(uuids):
    Instance.objects.filter(uuid__in=uuids).delete()


def dict2instancexml(jsform, form_id):
    dd = {'form_id': form_id}
    xml_head = u"<?xml version='1.0' ?><root id='%(form_id)s'>" % dd
    xml_tail = u"</root>" % dd

    return xml_head + dict2xml(jsform) + xml_tail


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

        for key in row.keys(): # seems faster than a comprehension
            # remove metadata (keys starting with '_')
            if key.startswith('_'):
                del row[key]
            # process nested data e.g x[formhub/uuid] => x[formhub][uuid]
            if r'/' in key:
                p, c = key.split('/')
                row[p] = { c : row[key] }
                del row[key]

        xml_file = StringIO(dict2instancexml(dict_lists2strings(row), row_uuid))
        error, instance = safe_create_instance(
            username, xml_file, [], row_uuid, None)
        if error is not None:
            # there has to be a more elegant way to roll back
            # the following is a stop-gap
            csv_submit_rollback(rollback_uuids)
            raise CSVImportException(error)
