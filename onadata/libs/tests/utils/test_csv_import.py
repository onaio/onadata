from __future__ import unicode_literals

import os
import re
from builtins import open
from io import BytesIO
from xml.etree.ElementTree import fromstring

import mock
import unicodecsv as ucsv
from celery.backends.rpc import BacklogLimitExceeded
from django.conf import settings
from mock import patch

from onadata.apps.logger.models import Instance, XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.messaging.constants import \
    XFORM, SUBMISSION_EDITED, SUBMISSION_CREATED
from onadata.libs.utils import csv_import
from onadata.libs.utils.csv_import import get_submission_meta_dict
from onadata.libs.utils.user_auth import get_user_default_project


def strip_xml_uuid(s):
    return re.sub(b'\S*uuid\S*', b'', s.rstrip(b'\n'))  # noqa


class CSVImportTestCase(TestBase):
    def setUp(self):
        super(CSVImportTestCase, self).setUp()
        self.fixtures_dir = os.path.join(settings.PROJECT_ROOT, 'libs',
                                         'tests', 'utils', 'fixtures')
        self.good_csv = open(os.path.join(self.fixtures_dir, 'good.csv'), 'rb')
        self.bad_csv = open(os.path.join(self.fixtures_dir, 'bad.csv'), 'rb')
        self.xls_file_path = os.path.join(self.fixtures_dir, 'tutorial.xls')
        self.good_xls = open(os.path.join(self.fixtures_dir, 'good.xls'), 'rb')

    def test_get_submission_meta_dict(self):
        self._publish_xls_file(self.xls_file_path)
        xform = XForm.objects.get()
        meta = get_submission_meta_dict(xform, None)
        self.assertEqual(len(meta), 2)
        self.assertTrue('instanceID' in meta[0])
        self.assertEqual(meta[1], 0)

        instance_id = 'uuid:9118a3fc-ab99-44cf-9a97-1bb1482d8e2b'
        meta = get_submission_meta_dict(xform, instance_id)
        self.assertTrue('instanceID' in meta[0])
        self.assertEqual(meta[0]['instanceID'], instance_id)
        self.assertEqual(meta[1], 0)

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

        # Test rollback on error and user feedback
        with patch(
            'onadata.libs.utils.csv_import.safe_create_instance'
                ) as safe_create_mock:
            safe_create_mock.side_effect = [AttributeError]
            initial_count = self.xform.num_of_submissions
            resp = csv_import.submit_csv(
                self.user.username, self.xform, self.good_csv)
            self.assertEqual(resp, {'job_status': 'FAILURE'})
            self.xform.refresh_from_db()
            self.assertEqual(
                initial_count, self.xform.num_of_submissions)

    @patch('onadata.libs.utils.logger_tools.send_message')
    def test_submit_csv_edits(self, send_message_mock):
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
        # message sent upon submission edit
        self.assertTrue(send_message_mock.called)
        send_message_mock.called_with(self.xform.id, XFORM, SUBMISSION_EDITED)

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
        xls_file_path = os.path.join(self.fixtures_dir, 'space_in_header.xlsx')
        self._publish_xls_file(xls_file_path)
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

            def get(self):
                return {'job_status': 'SUCCESS'}

        AsyncResult.return_value = MockAsyncResult()
        result = csv_import.get_async_csv_submission_status('x-y-z')
        self.assertEqual(result, {'job_status': 'SUCCESS'})

        class MockAsyncResult2(object):
            def __init__(self):
                self.result = self.state = 'PROGRESS'
                self.info = {
                    "info": [],
                    "job_status": "PROGRESS",
                    "progress": 4000,
                    "total": 70605
                }

        AsyncResult.return_value = MockAsyncResult2()
        result = csv_import.get_async_csv_submission_status('x-y-z')
        self.assertEqual(result, {'info': [], 'job_status': 'PROGRESS',
                                  'progress': 4000, 'total': 70605})

        class MockAsyncResultIOError(object):
            def __init__(self):
                self.result = IOError("File not found!")
                self.state = 'FAILURE'

        AsyncResult.return_value = MockAsyncResultIOError()
        result = csv_import.get_async_csv_submission_status('x-y-z')
        self.assertEqual(result,
                         {'error': 'File not found!',
                          'job_status': 'FAILURE'})

        # shouldn't fail if info is not of type dict
        class MockAsyncResult2(object):
            def __init__(self):
                self.result = self.state = 'PROGRESS'
                self.info = None

        AsyncResult.return_value = MockAsyncResult2()
        result = csv_import.get_async_csv_submission_status('x-y-z')
        self.assertEqual(result, {'job_status': 'PROGRESS'})

    def test_submission_xls_to_csv(self):
        """Test that submission_xls_to_csv converts to csv"""
        c_csv_file = csv_import.submission_xls_to_csv(
            self.good_xls)

        c_csv_file.seek(0)
        c_csv_reader = ucsv.DictReader(c_csv_file, encoding='utf-8-sig')
        g_csv_reader = ucsv.DictReader(self.good_csv, encoding='utf-8-sig')

        self.assertEqual(
            g_csv_reader.fieldnames[10], c_csv_reader.fieldnames[10])

    @mock.patch('onadata.libs.utils.csv_import.safe_create_instance')
    def test_submit_csv_instance_id_consistency(self, safe_create_instance):
        self._publish_xls_file(self.xls_file_path)
        self.xform = XForm.objects.get()

        safe_create_instance.return_value = {}
        single_csv = open(os.path.join(self.fixtures_dir, 'single.csv'), 'rb')
        csv_import.submit_csv(self.user.username, self.xform, single_csv)
        xml_file_param = BytesIO(
            open(os.path.join(self.fixtures_dir, 'single.xml'), 'rb').read())
        safe_create_args = list(safe_create_instance.call_args[0])

        instance_xml = fromstring(safe_create_args[1].getvalue())
        single_instance_xml = fromstring(xml_file_param.getvalue())

        instance_id = [
            m.find('instanceID').text for m in instance_xml.findall('meta')][0]
        single_instance_id = [m.find('instanceID').text for m in
                              single_instance_xml.findall('meta')][0]

        self.assertEqual(
            len(instance_id), len(single_instance_id),
            "Same uuid length in generated xml")

    @patch('onadata.libs.utils.logger_tools.send_message')
    def test_data_upload(self, send_message_mock):
        """Data upload for submissions with no uuids"""
        self._publish_xls_file(self.xls_file_path)
        self.xform = XForm.objects.get()
        count = Instance.objects.count()
        single_csv = open(os.path.join(
            self.fixtures_dir, 'single_data_upload.csv'), 'rb')
        csv_import.submit_csv(self.user.username, self.xform, single_csv)
        self.xform.refresh_from_db()
        self.assertEqual(self.xform.num_of_submissions, count + 1)
        # message sent upon submission creation
        self.assertTrue(send_message_mock.called)
        send_message_mock.called_with(self.xform.id, XFORM, SUBMISSION_CREATED)

    def test_excel_date_conversion(self):
        """Convert date from 01/01/1900 to 01-01-1900"""
        date_md_form = """
        | survey |
        |        | type     | name  | label |
        |        | today    | today | Today |
        |        | text     | name  | Name  |
        |        | date     | tdate | Date  |
        |        | start    | start |       |
        |        | end      | end   |       |
        |        | dateTime | now   | Now   |
        | choices |
        |         | list name | name   | label  |
        | settings |
        |          | form_title | form_id |
        |          | Dates      | dates   |
        """

        self._create_user_and_login()
        data = {'name': 'data'}
        survey = self.md_to_pyxform_survey(date_md_form, kwargs=data)
        survey['sms_keyword'] = survey['id_string']
        project = get_user_default_project(self.user)
        xform = XForm(created_by=self.user, user=self.user,
                      xml=survey.to_xml(), json=survey.to_json(),
                      project=project)
        xform.save()
        date_csv = open(os.path.join(
            self.fixtures_dir, 'date.csv'), 'rb')
        date_csv.seek(0)

        csv_reader = ucsv.DictReader(date_csv, encoding='utf-8-sig')
        xl_dates = []
        xl_datetime = []
        # xl dates
        for row in csv_reader:
            xl_dates.append(row.get('tdate'))
            xl_datetime.append(row.get('now'))

        csv_import.submit_csv(self.user.username, xform, date_csv)
        # converted dates
        conv_dates = [instance.json.get('tdate')
                      for instance in Instance.objects.filter(
                xform=xform).order_by('date_created')]
        conv_datetime = [instance.json.get('now')
                         for instance in Instance.objects.filter(
                xform=xform).order_by('date_created')]

        self.assertEqual(xl_dates, ['3/1/2019', '2/26/2019'])
        self.assertEqual(
            xl_datetime,
            [u'6/12/2020 13:20', u'2019-03-11T16:00:51.147+02:00'])
        self.assertEqual(
            conv_datetime,
            [u'2020-06-12T13:20:00',
             u'2019-03-11T16:00:51.147000+02:00'])
        self.assertEqual(conv_dates, ['2019-03-01', '2019-02-26'])

    def test_enforces_data_type_and_rollback(self):
        """
        Test that data type constraints are enforced and instances created
        during the process are rolled back
        """
        # Test integer constraint is enforced
        xls_file_path = os.path.join(settings.PROJECT_ROOT, "apps", "main",
                                     "tests", "fixtures", "tutorial.xls")
        self._publish_xls_file(xls_file_path)
        self.xform = XForm.objects.last()

        bad_data = open(
            os.path.join(self.fixtures_dir, 'bad_data.csv'),
            'rb')
        count = Instance.objects.count()
        result = csv_import.submit_csv(self.user.username, self.xform,
                                       bad_data)

        expected_error = (
            "Invalid CSV data imported in row(s): {1: ['Unknown date format(s)"
            ": 2014-0903', 'Unknown datetime format(s): sdsa', "
            "'Unknown integer format(s): 21.53'], 2: ['Unknown integer format"
            "(s): 22.32'], 4: ['Unknown date format(s): 2014-0900'], "
            "5: ['Unknown date format(s): 2014-0901'], 6: ['Unknown "
            "date format(s): 2014-0902'], 7: ['Unknown date format(s):"
            " 2014-0903']}")
        self.assertEqual(
            result.get('error'),
            expected_error)
        # Assert all created instances were rolled back
        self.assertEqual(count, Instance.objects.count())
