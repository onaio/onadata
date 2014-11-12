# import mock
import os
from cStringIO import StringIO
from django.conf import settings
from onadata.libs.utils import csv_import
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models import Instance
from onadata.apps.main.tests.test_base import TestBase


class CSVImportTestCase(TestBase):

    def setUp(self):
        super(CSVImportTestCase, self).setUp()
        self.fixtures_dir = os.path.join(settings.PROJECT_ROOT,
                                         'libs', 'tests', 'fixtures')
        self.good_csv = open(os.path.join(self.fixtures_dir, 'good.csv'))
        self.bad_csv = open(os.path.join(self.fixtures_dir, 'bad.csv'))
        xls_file_path = os.path.join(self.fixtures_dir, 'tutorial.xls')
        self._publish_xls_file(xls_file_path)
        self.xform = XForm.objects.get()

    def test_submit_csv_param_sanity_check(self):
        with self.assertRaises(Exception):
            # pass an int to check failure
            csv_import.submit_csv(u'userX', XForm(), 123456)

    # @mock.patch('onadata.libs.utils.csv_import.safe_create_instance')
    # def test_submit_csv_xml_params(self, safe_create_instance):
    #     safe_create_instance.return_value = [None, {}]
    #     single_csv = open(os.path.join(self.fixtures_dir, 'single.csv'))
    #     csv_import.submit_csv(self.user.username, self.xform, single_csv)
    #     xml_file_param = StringIO(open(os.path.join(self.fixtures_dir,
    #                                                 'single.csv')).read())
    #     safe_create_instance.assert_called_with(self.user.username,
    #                                             xml_file_param, [],
    #                                             self.xform.uuid, None)

    def test_submit_csv_and_rollback(self):
        count = Instance.objects.count()
        csv_import.submit_csv(self.user.username, self.xform, self.good_csv)
        self.assertEqual(Instance.objects.count(),
                         count + 9, u'submit_csv test Failed!')
        # Check that correct # of submissions belong to our user
        self.assertEqual(
            Instance.objects.filter(user=self.user).count(),
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
        self.assertEqual(Instance.objects.count(),
                         count, u'submit_csv edits #2 test Failed!')
