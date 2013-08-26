import os
import json
from django.conf import settings
from main.tests.test_base import MainTestCase
from django.core.urlresolvers import reverse
from odk_logger.models import ZiggyInstance
from odk_logger.views import ziggy_submissions

mongo_ziggys = settings.MONGO_DB.ziggys


class TestZiggy(MainTestCase):
    ziggy_submission_url = reverse(ziggy_submissions)
    village_profile_json_path = os.path.join(
        os.path.dirname(__file__), 'fixtures', 'ziggy', 'village_profile.json')
    cc_monthly_json_path = os.path.join(
        os.path.dirname(__file__), 'fixtures', 'ziggy',
        'cc_monthly_report.json')
    ENTITY_ID = '9e7ee7c3-3071-4cb5-881f-f71572101f35'

    def setUp(self):
        super(TestZiggy, self).setUp()
        # todo: create c user for now
        self._create_user('c', 'c1')

    def make_ziggy_submission(self, path):
        with open(path) as f:
            data = f.read()
        return self.client.post(self.ziggy_submission_url, data,
                                content_type='application/json')

    def test_ziggy_submissions_post_url(self):
        num_ziggys = ZiggyInstance.objects.count()
        response = self.make_ziggy_submission(self.village_profile_json_path)
        self.assertEqual(response.status_code, 201)
        # check instance was created in db
        self.assertEqual(ZiggyInstance.objects.count(), num_ziggys + 1)
        # check that instance was added to mongo
        num_entities = mongo_ziggys.find(
            {'_id': self.ENTITY_ID}).count()
        self.assertEqual(num_entities, 1)

    def test_ziggy_submission_post_update(self):
        num_ziggys = ZiggyInstance.objects.count()
        response = self.make_ziggy_submission(self.village_profile_json_path)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ZiggyInstance.objects.count(), num_ziggys + 1)

        # make update submission
        response = self.make_ziggy_submission(self.cc_monthly_json_path)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ZiggyInstance.objects.count(), num_ziggys + 2)

        # check that we only end up with a single updated object within mongo
        entities = [r for r in mongo_ziggys.find({'_id': self.ENTITY_ID})]
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

    def test_ziggy_post_sorts_by_timestamp(self):
        pass