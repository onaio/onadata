import mock
import unittest
import os
from django.conf import settings
from django.test import TransactionTestCase
from onadata.libs.utils import csv_import
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models import Instance
from onadata.apps.logger.xform_instance_parser import DuplicateInstance
from django.contrib.auth.models import AnonymousUser, User
from onadata.apps.main.tests.test_base import TestBase


class CSVImportTestCase(unittest.TestCase):

    def setUp(self):
        super(CSVImportTestCase, self).setUp()

    @mock.patch('onadata.libs.utils.csv_import.get_submission_meta_dict',
                mock.Mock(return_value={'instanceID': '1234567'}))
    def test_submit_csv_param_sanity_check(self):
        with self.assertRaises(Exception):
            # pass an int to check failure
            csv_import.submit_csv(u'userX', XForm(), 123456)



class CSVImportTransactionTestCase(TestBase):

    def setUp(self):
        super(CSVImportTransactionTestCase, self).setUp()
        fixtures_dir = os.path.join(settings.PROJECT_ROOT,
                                    'libs', 'tests', 'fixtures')
        self.good_csv = open(os.path.join(fixtures_dir, 'good.csv'))
        self.bad_csv = open(os.path.join(fixtures_dir, 'bad.csv'))
        # xls_file_path = open(os.path.join(fixtures_dir, 'tutorial.xls'))
        xls_file_path = os.path.join(fixtures_dir, 'tutorial.xls')

        self.user = User.objects.create_user(username='TestUser',
                                             email='T@X',
                                             password='secret')
        self._publish_xls_file(xls_file_path)
        self.xform = XForm.objects.get()

    def test_submit_csv_rollback(self):
        count = Instance.objects.count()
        with self.assertRaises(ValueError):
            csv_import.submit_csv(u'TestUser', self.xform, self.bad_csv)
        self.assertEqual(
            Instance.objects.count(),
            count, u'submit_csv rollback failed!')

    def test_submit_csv(self):
        count = Instance.objects.count()
        csv_import.submit_csv(u'TestUser', self.xform, self.good_csv)
        self.assertEqual(
            Instance.objects.count(),
            count + 9, u'submit_csv test Failed!')

    def test_submit_csv_edits(self):
        csv_import.submit_csv(u'TestUser', self.xform, self.good_csv)
        self.assertEqual(
            len(Instance.objects.filter(uuid__in=self.submit_uuids)),
            9, u'submit_csv test Failed!')

        self.good_csv.seek(0)

        count = Instance.objects.count()
        csv_import.submit_csv(u'TestUser', self.xform, self.good_csv)
        self.assertEqual(
            Instance.objects.count(),
            count, u'submit_csv test Failed!')
