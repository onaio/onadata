#!/usr/bin/env python

import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = os.environ.get('DJANGO_SETTINGS_MODULE', 
                                                      'settings')
import tempfile

from odk_viewer.pandas_mongo_bridge import NoRecordsFoundError, FlatExport

USERNAME = u'litreportcards'
ID_STRING = u'repeat_test'

USERNAME = u'mberg'
ID_STRING = u'hh_polio_survey'


def launch(filename):
    import envoy
    envoy.run('/usr/bin/xdg-open %s' % filename)

def export_csv(id_string=ID_STRING, username=USERNAME):

    query = None
    # csv_dataframe_builder = FlatCSVDataFrameBuilder(username, id_string, query)
    csv_dataframe_builder = FlatExport(username, id_string, query)
    try:
        fileh, filename = tempfile.mkstemp(suffix='.csv')
        csv_dataframe_builder.export_to(filename)
        os.close(fileh)
        
        print(filename)

    except NoRecordsFoundError:
        print(u"No records found to export")

    return filename

if __name__ == '__main__':
    filename = export_csv(ID_STRING, USERNAME)
    if len(sys.argv) > 1 and sys.argv[-1].lower() == 'launch':
        launch(filename)