import os
import re
import json
import requests

from bson import ObjectId
from django.conf import settings
from django.core.urlresolvers import reverse
from httmock import urlmatch, HTTMock

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import ZiggyInstance
from onadata.apps.logger.models.ziggy_instance import (
    ziggy_to_formhub_instance, rest_service_ziggy_submission)
from onadata.apps.logger.views import ziggy_submissions
from onadata.apps.restservice.models import RestService

mongo_ziggys = settings.MONGO_DB.ziggys
ziggy_submission_url = reverse(ziggy_submissions, kwargs={'username': 'bob'})
village_profile_xls_path = os.path.join(
    os.path.dirname(__file__), 'fixtures', 'ziggy', 'village_profile.xls')
village_profile_json_path = os.path.join(
    os.path.dirname(__file__), 'fixtures', 'ziggy', 'village_profile.json')
cc_monthly_xls_path = os.path.join(
    os.path.dirname(__file__), 'fixtures', 'ziggy',
    'cc_monthly_report_form.xls')
cc_monthly_json_path = os.path.join(
    os.path.dirname(__file__), 'fixtures', 'ziggy',
    'cc_monthly_report.json')
ENTITY_ID = '9e7ee7c3-3071-4cb5-881f-f71572101f35'


class TestZiggySubmissions(TestBase):
    def setUp(self):
        super(TestZiggySubmissions, self).setUp()
        # publish xforms
        self._publish_xls_file(village_profile_xls_path)
        self._publish_xls_file(cc_monthly_xls_path)

    def tearDown(self):
        # clear mongo db after each test
        settings.MONGO_DB.ziggys.drop()

    def make_ziggy_submission(self, path):
        with open(path) as f:
            data = f.read()
        return self.client.post(ziggy_submission_url, data,
                                content_type='application/json')

    def test_ziggy_submissions_post_url(self):
        self._ziggy_submissions_post_url()

    def _ziggy_submissions_post_url(self):
        num_ziggys = ZiggyInstance.objects.count()
        response = self.make_ziggy_submission(village_profile_json_path)
        self.assertEqual(response.status_code, 201)
        # check instance was created in db
        self.assertEqual(ZiggyInstance.objects.count(), num_ziggys + 1)
        # check that instance was added to mongo
        num_entities = mongo_ziggys.find(
            {'_id': ENTITY_ID}).count()
        self.assertEqual(num_entities, 1)

    def test_ziggy_submissions_view(self):
        self._ziggy_submissions_post_url()
        response = self.client.get(
            ziggy_submission_url,
            data={'timestamp': 0, 'reporter-id': self.user.username}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 1)
        del data[0]['serverVersion']
        del data[0]['_id']
        with open(village_profile_json_path) as f:
            expected_data = json.load(f)
            expected_data[0]['formInstance'] = json.loads(
                expected_data[0]['formInstance'])
            data[0]['formInstance'] = json.loads(data[0]['formInstance'])
            self.assertEqual(expected_data, data)

    def test_ziggy_submissions_view_invalid_timestamp(self):
        self._ziggy_submissions_post_url()
        response = self.client.get(
            ziggy_submission_url,
            data={'timestamp': 'k', 'reporter-id': self.user.username}
        )
        self.assertEqual(response.status_code, 400)

    def test_ziggy_submission_post_update(self):
        num_ziggys = ZiggyInstance.objects.count()
        response = self.make_ziggy_submission(village_profile_json_path)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ZiggyInstance.objects.count(), num_ziggys + 1)

        # make update submission
        response = self.make_ziggy_submission(cc_monthly_json_path)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ZiggyInstance.objects.count(), num_ziggys + 2)

        # check that we only end up with a single updated object within mongo
        entities = [r for r in mongo_ziggys.find({'_id': ENTITY_ID})]
        self.assertEqual(len(entities), 1)

        # check that the sagContactNumber field exists and is unmodified
        entity = entities[0]
        matching_fields = filter(
            ZiggyInstance.field_by_name_exists('sagContactNumber'),
            json.loads(entity['formInstance'])['form']['fields'])
        self.assertEqual(len(matching_fields), 1)
        self.assertEqual(matching_fields[0]['value'], '020-123456')

        # todo: check that the new data has been added
        matching_fields = filter(
            ZiggyInstance.field_by_name_exists('reportingMonth'),
            json.loads(entity['formInstance'])['form']['fields'])
        self.assertEqual(len(matching_fields), 1)
        self.assertEqual(matching_fields[0]['value'], '10-2013')

    def test_merge_ziggy_form_instances(self):
        instance_1 = [
            {'name': 'village_name', 'value': 'Ugenya'},
            {'name': 'village_code', 'value': '012-123'},
            {'name': 'village_contact_no', 'value': '050 123456'}]

        instance_2 = [
            {'name': 'village_name', 'value': 'Uriya'},
            {'name': 'village_contact_no', 'value': '050 876543'},
            {'name': 'num_latrines', 'value': 23}]

        merged_instance = ZiggyInstance.merge_ziggy_form_instances(
            instance_1, instance_2)
        expected_merged_instance = [
            # named changed to Uriya
            {'name': 'village_name', 'value': 'Uriya'},
            # village code un-touched
            {'name': 'village_code', 'value': '012-123'},
            # contact no  updated
            {'name': 'village_contact_no', 'value': '050 876543'},
            # num latrines is a new field
            {'name': 'num_latrines', 'value': 23}]

        self.assertEqual(
            filter(ZiggyInstance.field_by_name_exists(
                'village_name'), merged_instance)[0],
            filter(ZiggyInstance.field_by_name_exists(
                'village_name'), expected_merged_instance)[0])
        self.assertEqual(
            filter(ZiggyInstance.field_by_name_exists(
                'village_code'), merged_instance)[0],
            filter(ZiggyInstance.field_by_name_exists(
                'village_code'), expected_merged_instance)[0])
        self.assertEqual(
            filter(ZiggyInstance.field_by_name_exists(
                'village_contact_no'), merged_instance)[0],
            filter(ZiggyInstance.field_by_name_exists(
                'village_contact_no'), expected_merged_instance)[0])
        self.assertEqual(
            filter(ZiggyInstance.field_by_name_exists(
                'num_latrines'), merged_instance)[0],
            filter(ZiggyInstance.field_by_name_exists(
                'num_latrines'), expected_merged_instance)[0])

    def test_submission_when_xform_doesnt_exist_works(self):
        pass

    def test_ziggy_post_sorts_by_timestamp(self):
        pass


@urlmatch(netloc=r'^(.*)example\.com', path='^/f2dhis2')
def f2dhis_mock(url, request):
    match = re.match(r'.*f2dhis2/(.+)/post/(.+)$', request.url)
    if match is not None:
        id_string, uuid = match.groups()
        record = settings.MONGO_DB.instances.find_one(
            {'_uuid': ObjectId(uuid)})
        if record is not None:
            res = requests.Response()
            res.status_code = 200
            res._content = "{'status': true, 'contents': 'OK'}"
            return res


class TestZiggyRestService(TestBase):
    def setUp(self):
        super(TestZiggyRestService, self).setUp()
        # publish xform
        self._publish_xls_file_and_set_xform(cc_monthly_xls_path)
        # add a dhis service
        RestService.objects.create(
            name='f2dhis2',
            xform=self.xform,
            service_url='http://example.com/f2dhis2/'
            '%(id_string)s/post/%(uuid)s')

    def test_rest_service_ziggy_submission(self):
        with open(cc_monthly_json_path) as f:
            json_post = json.load(f)
        ziggy_json = json_post[0]
        zi = ZiggyInstance.create_ziggy_instance(self.user, ziggy_json,
                                                 self.user)
        # check that the HTTP request was made
        with HTTMock(f2dhis_mock):
            services_called = rest_service_ziggy_submission(
                ZiggyInstance, zi, False, True, False)
            # make sure a service was called
            self.assertEqual(services_called, 1)

    def test_ziggy_to_formhub_instance(self):
        with open(cc_monthly_json_path) as f:
            json_post = json.load(f)
        ziggy_json = json_post[0]
        zi = ZiggyInstance.create_ziggy_instance(self.user, ziggy_json,
                                                 self.user)
        formhub_dict = ziggy_to_formhub_instance(zi)
        expected_formhub_dict = {
            'village_name': 'dygvbh',
            'village_code': 'fjhgh',
            'gps': '',
            'reporting_month': '10-2013',
            'households': '12',
            'village_population': '2',
            'improved_latrines': '5',
            'latrines_smooth_cleanable_floor': '45',
            'latrines_with_lid': '12',
            'latrines_with_superstructure': '8',
            'latrines_signs_of_use': '5',
            'latrines_hand_washers': '12',
            'latrines_all_improved_reqs': '',
            'households_quality_checked': '4',
            'checks_accurate': '9',
            'today': '2013-08-23',
            '_userform_id': 'bob_cc_monthly_report_form'
        }
        self.assertDictEqual(formhub_dict, expected_formhub_dict)
