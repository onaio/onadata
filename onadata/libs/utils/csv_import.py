import unicodecsv as ucsv
from cStringIO import StringIO
from ondata.apps.api.viewsets.xform_submission_api import dict_lists2strings
from onadata.libs.utils.logger_tools import dict2xform, safe_create_instance
from django.db import transaction


class CSVImportException(Exception):
    pass


def submit_csv(username, request, csv_data):

    if isinstance(csv_data, (str, unicode)):
        csv_data = StringIO(csv_data)
    elif not isinstance(csv_data, file):
        raise TypeError(u'Invalid param type for `csv_data`. '
                        'Expected file, String or Unicode but '
                        'got {} instead.'.format(type(csv_data).__name__))

    csv_reader = ucsv.DictReader(csv_data)
    with transaction.atomic():
        for row in csv_reader:
            # fetch submission uuid before nuking row metadata
            _uuid = row.get('_uuid')
            # nuke metadata (keys starting with '_')
            for key in row.keys():
                if key.startswith('_'):
                    del row[key]
            xml_file = StringIO(dict2xform(dict_lists2strings(row), _uuid))
            error, instance = safe_create_instance(
                username, xml_file, [], None, None)
            if error is None:
                raise CSVImportException(error)
