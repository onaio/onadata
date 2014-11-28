import mock
import os
import re
from cStringIO import StringIO
from django.conf import settings
from onadata.libs.utils import csv_import
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models import Instance
from onadata.apps.main.tests.test_base import TestBase


def strip_xml_uuid(s):
    return re.sub('\S*uuid\S*', '', s.rstrip('\n'))


class CSVImportTestCase(TestBase):

    def setUp(self):
        super(CSVImportTestCase, self).setUp()
        self.fixtures_dir = os.path.join(settings.PROJECT_ROOT,
                                         'libs', 'utils', 'tests', 'fixtures')
        self.good_csv = open(os.path.join(self.fixtures_dir, 'good.csv'))
        self.bad_csv = open(os.path.join(self.fixtures_dir, 'bad.csv'))
        xls_file_path = os.path.join(self.fixtures_dir, 'tutorial.xls')
        self._publish_xls_file(xls_file_path)
        self.xform = XForm.objects.get()

    def test_submit_csv_param_sanity_check(self):
        resp = csv_import.submit_csv(u'userX', XForm(), 123456)
        self.assertIsNotNone(resp.get('error'))

    @mock.patch('onadata.libs.utils.csv_import.safe_create_instance')
    def test_submit_csv_xml_params(self, safe_create_instance):
        safe_create_instance.return_value = {}
        single_csv = open(os.path.join(self.fixtures_dir, 'single.csv'))
        csv_import.submit_csv(self.user.username, self.xform, single_csv)
        xml_file_param = StringIO(open(os.path.join(self.fixtures_dir,
                                                    'single.xml')).read())
        safe_create_args = list(safe_create_instance.call_args[0])

        self.assertEqual(safe_create_args[0],
                         self.user.username,
                         u'Wrong username passed')
        self.assertEqual(strip_xml_uuid(safe_create_args[1].getvalue()),
                         strip_xml_uuid(xml_file_param.getvalue()),
                         u'Wrong xml param passed')
        self.assertEqual(safe_create_args[2], [],
                         u'Wrong media array param passed')
        self.assertEqual(safe_create_args[3], self.xform.uuid,
                         u'Wrong xform uuid passed')
        self.assertEqual(safe_create_args[4], None)

    @mock.patch('onadata.libs.utils.csv_import.safe_create_instance')
    @mock.patch('onadata.libs.utils.csv_import.dict2xmlsubmission')
    def test_submit_csv_xml_location_property_test(
            self, d2x, safe_create_instance):
        safe_create_instance.return_value = [None, ]
        single_csv = open(os.path.join(self.fixtures_dir, 'single.csv'))
        csv_import.submit_csv(self.user.username, self.xform, single_csv)

        test_location_val = '83.3595 -32.8601 0 1'
        test_location2_val = '21.22474 -10.5601 50000 200'

        self.assertNotEqual(d2x.call_args, None,
                            u'dict2xmlsubmission not called')

        call_dict = d2x.call_args[0][0]

        self.assertEqual(call_dict.get('test_location'),
                         test_location_val, u'Location prop test fail')
        self.assertEqual(call_dict.get('test_location2'),
                         test_location2_val, u'Location2 prop test fail')

    def test_submit_csv_and_rollback(self):
        count = Instance.objects.count()
        csv_import.submit_csv(self.user.username, self.xform, self.good_csv)
        self.assertEqual(Instance.objects.count(),
                         count + 9, u'submit_csv test Failed!')
        # Check that correct # of submissions belong to our user
        self.assertEqual(Instance.objects.filter(user=self.user).count(),
                         count + 8, u'submit_csv username check failed!')

    def test_submit_csv_edits(self):
        csv_import.submit_csv(self.user.username, self.xform, self.good_csv)
        self.assertEqual(Instance.objects.count(),
                         9, u'submit_csv edits #1 test Failed!')

        edit_csv = open(os.path.join(self.fixtures_dir, 'edit.csv'))
        edit_csv_str = edit_csv.read()

        edit_csv = StringIO(edit_csv_str.format(
            *[x.get('uuid') for x in Instance.objects.values('uuid')]))

        count = Instance.objects.count()
        csv_import.submit_csv(self.user.username, self.xform, edit_csv)
        self.assertEqual(Instance.objects.count(), count,
                         u'submit_csv edits #2 test Failed!')

    def test_import_non_utf8_csv(self):
        count = Instance.objects.count()
        non_utf8_csv = open(os.path.join(self.fixtures_dir, 'non_utf8.csv'))
        result = csv_import.submit_csv(self.user.username,
                                       self.xform, non_utf8_csv)
        self.assertEqual(result.get('error'),
                         u'CSV file must be utf-8 encoded',
                         u'Incorrect error message returned.')
        self.assertEqual(Instance.objects.count(), count,
                         u'Non unicode csv import rollback failed!')

    def test_reject_spaces_in_headers(self):
        non_utf8csv = open(os.path.join(self.fixtures_dir, 'header_space.csv'))
        result = csv_import.submit_csv(self.user.username,
                                       self.xform, non_utf8csv)
        self.assertEqual(result.get('error'),
                         u'CSV file fieldnames should not contain spaces',
                         u'Incorrect error message returned.')

    def test_nested_geo_paths_csv(self):
        good_csv = open(os.path.join(self.fixtures_dir, 'another_good.csv'))
        csv_import.submit_csv(self.user.username, self.xform, good_csv)
        self.assertEqual(Instance.objects.count(),
                         9, u'submit_csv edits #1 test Failed!')


    @mock.patch('onadata.libs.utils.csv_import._submit_csv')
    def test_submit_csv_long_running(self, _submit_csv):

        class mock_task:
            id = 'Mock_ID'

        _submit_csv.delay = mock.Mock(return_value=mock_task())
        huge_csv = open(os.path.join(self.fixtures_dir, 'huge.csv'))
        result = csv_import.submit_csv(self.user.username, self.xform, huge_csv)
        self.assertEqual(result.get('task_uuid'), 'Mock_ID')
