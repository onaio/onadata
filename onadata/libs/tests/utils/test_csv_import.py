from __future__ import unicode_literals

import os
import re
from builtins import open
from io import BytesIO

from django.conf import settings

import mock
from celery.backends.amqp import BacklogLimitExceeded

from onadata.apps.logger.models import Instance, XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils import csv_import


def strip_xml_uuid(s):
    return re.sub(b'\S*uuid\S*', b'', s.rstrip(b'\n'))


class CSVImportTestCase(TestBase):
    def setUp(self):
        super(CSVImportTestCase, self).setUp()
        self.fixtures_dir = os.path.join(settings.PROJECT_ROOT, 'libs',
                                         'tests', 'utils', 'fixtures')
        self.good_csv = open(os.path.join(self.fixtures_dir, 'good.csv'), 'rb')
        self.bad_csv = open(os.path.join(self.fixtures_dir, 'bad.csv'), 'rb')
        self.xls_file_path = os.path.join(self.fixtures_dir, 'tutorial.xls')

    def test_submit_csv_param_sanity_check(self):
        resp = csv_import.submit_csv('userX', XForm(), 123456)
        self.assertIsNotNone(resp.get('error'))

    @mock.patch('onadata.libs.utils.csv_import.safe_create_instance')
    def test_submit_csv_xml_params(self, safe_create_instance):
        self._publish_xls_file(self.xls_file_path)
        self.xform = XForm.objects.get()

        safe_create_instance.return_value = {}
        single_csv = open(os.path.join(self.fixtures_dir, 'single.csv'), 'rb')
        csv_import.submit_csv(self.user.username, self.xform, single_csv)
        xml_file_param = BytesIO(
            open(os.path.join(self.fixtures_dir, 'single.xml'), 'rb').read())
        safe_create_args = list(safe_create_instance.call_args[0])

        self.assertEqual(safe_create_args[0], self.user.username,
                         'Wrong username passed')
        self.assertEqual(
            strip_xml_uuid(safe_create_args[1].getvalue()),
            strip_xml_uuid(xml_file_param.getvalue()),
            'Wrong xml param passed')
        self.assertEqual(safe_create_args[2], [],
                         'Wrong media array param passed')
        self.assertEqual(safe_create_args[3], self.xform.uuid,
                         'Wrong xform uuid passed')
        self.assertEqual(safe_create_args[4], None)

    @mock.patch('onadata.libs.utils.csv_import.safe_create_instance')
    @mock.patch('onadata.libs.utils.csv_import.dict2xmlsubmission')
    def test_submit_csv_xml_location_property_test(self, d2x,
                                                   safe_create_instance):
        self._publish_xls_file(self.xls_file_path)
        self.xform = XForm.objects.get()
        safe_create_instance.return_value = [
            None,
        ]
        single_csv = open(os.path.join(self.fixtures_dir, 'single.csv'), 'rb')
        csv_import.submit_csv(self.user.username, self.xform, single_csv)

        test_location_val = '83.3595 -32.8601 0 1'
        test_location2_val = '21.22474 -10.5601 50000 200'

        self.assertNotEqual(d2x.call_args, None,
                            'dict2xmlsubmission not called')

        call_dict = d2x.call_args[0][0]

        self.assertEqual(
            call_dict.get('test_location'), test_location_val,
            'Location prop test fail')
        self.assertEqual(
            call_dict.get('test_location2'), test_location2_val,
            'Location2 prop test fail')

    def test_submit_csv_and_rollback(self):
        xls_file_path = os.path.join(settings.PROJECT_ROOT, "apps", "main",
                                     "tests", "fixtures", "tutorial.xls")
        self._publish_xls_file(xls_file_path)
        self.xform = XForm.objects.get()

        count = Instance.objects.count()
        csv_import.submit_csv(self.user.username, self.xform, self.good_csv)
        self.assertEqual(Instance.objects.count(), count + 9,
                         'submit_csv test Failed!')
        # Check that correct # of submissions belong to our user
        self.assertEqual(
            Instance.objects.filter(user=self.user).count(),
            count + 8,
            'submit_csv username check failed!')
        self.xform.refresh_from_db()
        self.assertEqual(self.xform.num_of_submissions, count + 9)

    def test_submit_csv_edits(self):
        xls_file_path = os.path.join(settings.PROJECT_ROOT, "apps", "main",
                                     "tests", "fixtures", "tutorial.xls")
        self._publish_xls_file(xls_file_path)
        self.xform = XForm.objects.get()

        csv_import.submit_csv(self.user.username, self.xform, self.good_csv)
        self.assertEqual(Instance.objects.count(), 9,
                         'submit_csv edits #1 test Failed!')

        edit_csv = open(os.path.join(self.fixtures_dir, 'edit.csv'))
        edit_csv_str = edit_csv.read()

        edit_csv = BytesIO(
            edit_csv_str.format(
                * [x.get('uuid') for x in Instance.objects.values('uuid')])
            .encode('utf-8'))

        count = Instance.objects.count()
        csv_import.submit_csv(self.user.username, self.xform, edit_csv)
        self.assertEqual(Instance.objects.count(), count,
                         'submit_csv edits #2 test Failed!')

    def test_import_non_utf8_csv(self):
        xls_file_path = os.path.join(self.fixtures_dir, "mali_health.xls")
        self._publish_xls_file(xls_file_path)
        self.xform = XForm.objects.get()

        count = Instance.objects.count()
        non_utf8_csv = open(os.path.join(self.fixtures_dir, 'non_utf8.csv'),
                            'rb')
        result = csv_import.submit_csv(self.user.username, self.xform,
                                       non_utf8_csv)
        self.assertEqual(
            result.get('error'), 'CSV file must be utf-8 encoded',
            'Incorrect error message returned.')
        self.assertEqual(Instance.objects.count(), count,
                         'Non unicode csv import rollback failed!')

    def test_reject_spaces_in_headers(self):
        self._publish_xls_file(self.xls_file_path)
        self.xform = XForm.objects.get()

        non_utf8csv = open(os.path.join(self.fixtures_dir, 'header_space.csv'),
                           'rb')
        result = csv_import.submit_csv(self.user.username, self.xform,
                                       non_utf8csv)
        self.assertEqual(
            result.get('error'),
            'CSV file fieldnames should not contain spaces',
            'Incorrect error message returned.')

    def test_nested_geo_paths_csv(self):
        self.xls_file_path = os.path.join(self.fixtures_dir,
                                          'tutorial-nested-geo.xls')
        self._publish_xls_file(self.xls_file_path)
        self.xform = XForm.objects.get()

        good_csv = open(os.path.join(self.fixtures_dir, 'another_good.csv'),
                        'rb')
        csv_import.submit_csv(self.user.username, self.xform, good_csv)
        self.assertEqual(Instance.objects.count(), 9,
                         'submit_csv edits #1 test Failed!')

    def test_csv_with_multiple_select_in_one_column(self):
        self.xls_file_path = os.path.join(self.fixtures_dir,
                                          'form_with_multiple_select.xlsx')
        self._publish_xls_file(self.xls_file_path)
        self.xform = XForm.objects.get()

        good_csv = open(
            os.path.join(self.fixtures_dir,
                         'csv_import_with_multiple_select.csv'),
            'rb')
        csv_import.submit_csv(self.user.username, self.xform, good_csv)
        self.assertEqual(Instance.objects.count(), 1,
                         'submit_csv edits #1 test Failed!')

    def test_csv_with_repeats_import(self):
        self.xls_file_path = os.path.join(self.this_directory, 'fixtures',
                                          'csv_export',
                                          'tutorial_w_repeats.xls')
        repeats_csv = open(
            os.path.join(self.this_directory, 'fixtures', 'csv_export',
                         'tutorial_w_repeats.csv'),
            'rb')
        self._publish_xls_file(self.xls_file_path)
        self.xform = XForm.objects.get()
        pre_count = self.xform.instances.count()
        csv_import.submit_csv(self.user.username, self.xform, repeats_csv)
        count = self.xform.instances.count()
        self.assertEqual(count, 1 + pre_count)

    def test_csv_with__more_than_4_repeats_import(self):
        self.xls_file_path = os.path.join(self.this_directory, 'fixtures',
                                          'csv_export',
                                          'tutorial_w_repeats.xls')
        repeats_csv = open(
            os.path.join(self.this_directory, 'fixtures', 'csv_export',
                         'tutorial_w_repeats_import.csv'),
            'rb')
        self._publish_xls_file(self.xls_file_path)
        self.xform = XForm.objects.get()
        pre_count = self.xform.instances.count()
        csv_import.submit_csv(self.user.username, self.xform, repeats_csv)

        count = self.xform.instances.count()
        self.assertEqual(count, 1 + pre_count)

        instance = self.xform.instances.last()
        # repeats should be 6
        self.assertEqual(6, len(instance.json.get('children')))

    @mock.patch('onadata.libs.utils.csv_import.AsyncResult')
    def test_get_async_csv_submission_status(self, AsyncResult):
        result = csv_import.get_async_csv_submission_status(None)
        self.assertEqual(result,
                         {'error': 'Empty job uuid',
                          'job_status': 'FAILURE'})

        class BacklogLimitExceededMockAsyncResult(object):
            def __init__(self):
                self.result = 0

            @property
            def state(self):
                raise BacklogLimitExceeded()

        AsyncResult.return_value = BacklogLimitExceededMockAsyncResult()
        result = csv_import.get_async_csv_submission_status('x-y-z')
        self.assertEqual(result, {'job_status': 'PENDING'})

        class MockAsyncResult(object):
            def __init__(self):
                self.result = self.state = 'SUCCESS'

        AsyncResult.return_value = MockAsyncResult()
        result = csv_import.get_async_csv_submission_status('x-y-z')
        self.assertEqual(result, {'job_status': 'SUCCESS'})

        class MockAsyncResult2(object):
            def __init__(self):
                self.result = self.state = 1

        AsyncResult.return_value = MockAsyncResult2()
        result = csv_import.get_async_csv_submission_status('x-y-z')
        self.assertEqual(result, 1)

        class MockAsyncResultIOError(object):
            def __init__(self):
                self.result = IOError("File not found!")
                self.state = 2

        AsyncResult.return_value = MockAsyncResultIOError()
        result = csv_import.get_async_csv_submission_status('x-y-z')
        self.assertEqual(result,
                         {'error': 'File not found!',
                          'job_status': 'FAILURE'})
