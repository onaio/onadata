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

    def test_submit_csv_param_sanity_check(self):
        with self.assertRaises(TypeError):
            # pass an int to check failure
            csv_import.submit_csv(u'userX', 123456)

        try:
            csv_import.submit_csv(u'userX', u'<Fake>XML</Fake>')
        except csv_import.CSVImportException:
            self.fail(u'submit_csv failed param sanity check')


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
        self.submit_uuids = [
            u'685dd371-4831-4fdc-a205-f285337dd98d',
            u'e92dad0d-ee3f-41eb-82d0-4cc0e7f12cb9',
            u'0b6d4344-6f64-41bc-8bab-a46a5493f9ad',
            u'15148861-93bc-45b8-ab56-6a9242c5a79d',
            u'137e1fb7-81a3-43ae-9039-6f6f599d55a6',
            u'fb0af0bf-d476-4136-a51f-13d84f6f9d62',
            u'f70bce6b-1785-43fd-8904-e8bb0975838a',
            u'db78c788-2ea3-4250-ab32-866e946811b6',
            u'0e1accb5-1c43-4789-ad2f-b9c663bbbc5d']

    def test_submit_csv_fail(self):
        with self.assertRaises(DuplicateInstance):
            csv_import.submit_csv(u'TestUser', self.xform, self.bad_csv)

        self.assertEqual(
            len(Instance.objects.filter(uuid__in=self.submit_uuids)),
            0, u'submit_csv atomicity test Failed!')

    def test_submit_csv(self):
        csv_import.submit_csv(u'TestUser', self.xform, self.good_csv)
        self.assertEqual(
            len(Instance.objects.filter(uuid__in=self.submit_uuids)),
            9, u'submit_csv test Failed!')

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
