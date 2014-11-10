import mock
import unittest
import os
from django.conf import settings
from django.test import TransactionTestCase
from cStringIO import StringIO
from onadata.libs.utils.csv_import import submit_csv
from onadata.libs.utils.csv_import import CSVImportException
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models import Instance
from onadata.apps.logger.xform_instance_parser import DuplicateInstance


class CSVImportTestCase(unittest.TestCase):

    def setUp(self):
        super(CSVImportTestCase, self).setUp()

    def test_submit_csv_param_sanity_check(self):
        with self.assertRaises(TypeError):
            # pass an int to check failure
            submit_csv(u'userX', 123456)

        try:
            submit_csv(u'userX', StringIO())
        except CSVImportException:
            self.fail(u'submit_csv failed param sanity check')


@mock.patch.multiple(XForm,
                     _set_title=mock.Mock(return_value=u'Mock Title'),
                     _set_id_string=mock.Mock(return_value=u'Mock id String'))
class CSVImportTransactionTestCase(TransactionTestCase):

    def setUp(self):
        fixtures_dir = os.path.join(settings.PROJECT_ROOT,
                                    'libs', 'tests', 'fixtures')
        self.good_csv = open(os.path.join(fixtures_dir, 'good.csv'))
        self.bad_csv = open(os.path.join(fixtures_dir, 'bad.csv'))
        Form = XForm(uuid=u'c37b9edf1e3443c69563e0c9c629546e')
        Form.save()
        self.submit_uuids = [
            u'949e096e-686b-11e4-b116-123b93f75cba',
            u'bee0b174-48b7-46cc-8294-7633ad5ccdec',
            u'a472c183-80c8-4ef7-8320-c5b2579de4a0',
            u'0b676052-e4e6-4ad1-bd43-b222db4b8925',
            u'1bccb787-d76e-4409-8f3e-2664f607b2d8',
            u'daeff6cb-0696-4534-b40a-7096a49cf0db',
            u'834d1c98-7217-47da-a918-21d32037ae74']

    def test_submit_csv_fail(self):
        with self.assertRaises(DuplicateInstance):
            submit_csv(u'userX', self.bad_csv)

        self.assertEqual(
            len(Instance.objects.filter(uuid__in=self.submit_uuids)),
            0, u'submit_csv atomicity test Failed!')

    def test_submit_csv(self):
        submit_csv(u'userX', self.good_csv)
        self.assertEqual(
            len(Instance.objects.filter(uuid__in=self.submit_uuids)),
            7, u'submit_csv test Failed!')
