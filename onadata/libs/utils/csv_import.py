import unicodecsv as ucsv
from cStringIO import StringIO
from ondata.apps.api.viewsets.xform_submission_api import dict_lists2strings
from onadata.libs.utils.logger_tools import dict2xform, safe_create_instance


def submit_csv(username, request, csv_data):

    if isinstance(csv_data, (str, unicode)):
        csv_data = StringIO(csv_data)
    elif not isinstance(csv_data, file):
        raise TypeError(u'Invalid param type for `csv_data`. '
                        'Expected file, String or Unicode but '
                        'got {} instead.'.format(type(csv_data).__name__))

    csv_reader = ucsv.DictReader(csv_data)
    for row in csv_reader:
        xml_file = StringIO(dict2xform(dict_lists2strings(row),
                                       row.get('_uuid')))
        safe_create_instance(username, xml_file, [], None, None)
