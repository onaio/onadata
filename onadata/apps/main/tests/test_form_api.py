import base64
import json

from django.core.urlresolvers import reverse
from django.test import RequestFactory

from onadata.apps.main.views import api
from onadata.apps.viewer.models.parsed_instance import ParsedInstance
from onadata.libs.utils.mongo import _decode_from_mongo, _encode_for_mongo
from onadata.apps.main.tests.test_base import TestBase


def dict_for_mongo_without_userform_id(parsed_instance):
    d = parsed_instance.to_dict_for_mongo()
    # remove _userform_id since its not returned by the API
    d.pop(ParsedInstance.USERFORM_ID)
    return d


class TestFormAPI(TestBase):

    def setUp(self):
        super(TestBase, self).setUp()
        self.factory = RequestFactory()
        self._create_user_and_login()
        self._publish_transportation_form_and_submit_instance()
        self.api_url = reverse(api, kwargs={
            'username': self.user.username,
            'id_string': self.xform.id_string
        })

    def test_api(self):
        request = self.factory.get(self.api_url, {})
        request.user = self.user
        response = api(request, self.user.username, self.xform.id_string)
        self.assertEqual(response.status_code, 200)
        data = dict_for_mongo_without_userform_id(
            self.xform.instances.all()[0].parsed_instance)
        find_d = json.loads(response.content)[0]

        # ensure all strings are unicode
        data = json.loads(json.dumps(data))

        self.assertEqual(find_d, data)

    def test_api_with_query(self):
        # query string
        query = '{"transport/available_transportation_types_to_referral_facil'\
                'ity":"none"}'
        data = {'query': query}
        response = self.client.get(self.api_url, data)
        self.assertEqual(response.status_code, 200)
        d = dict_for_mongo_without_userform_id(
            self.xform.instances.all()[0].parsed_instance)
        find_d = json.loads(response.content)[0]
        self.assertEqual(find_d, d)

    def test_api_query_no_records(self):
        # query string
        query = {
            "transport/available_transporation_types_to_referral_facility":
            "bicycle"
        }
        data = {'query': json.dumps(query)}
        response = self.client.get(self.api_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'[]')
        data['fields'] = '["_id"]'
        response = self.client.get(self.api_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'[]')

    def test_handle_bad_json(self):
        response = self.client.get(self.api_url, {'query': '{bad'})
        self.assertEqual(response.status_code, 400)

    def test_api_jsonp(self):
        # query string
        callback = 'jsonpCallback'
        response = self.client.get(self.api_url, {'callback': callback})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertEqual(content.startswith(callback + '('), True)
        self.assertEqual(content.endswith(')'), True)
        start = callback.__len__() + 1
        end = content.__len__() - 1
        content = content[start: end]
        d = dict_for_mongo_without_userform_id(
            self.xform.instances.all()[0].parsed_instance)
        find_d = json.loads(content)[0]
        self.assertEqual(find_d, d)

    def test_api_with_query_start_limit(self):
        for i in range(1, 3):
            self._submit_transport_instance(i)
        # query string
        data = {'start': 0, 'limit': 2}
        response = self.client.get(self.api_url, data)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 2)
        data['fields'] = '["_id"]'
        response = self.client.get(self.api_url, data)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 2)

    def test_api_with_query_invalid_start_limit(self):
        # query string
        query = '{"transport/available_transportation_types_to_referral_facil'\
                'ity":"none"}'
        data = {'query': query, 'start': -100, 'limit': -100}
        response = self.client.get(self.api_url, data)
        self.assertEqual(response.status_code, 400)

        data = {'query': query, 'start': 'invalid', 'limit': 'invalid'}
        response = self.client.get(self.api_url, data)
        self.assertEqual(response.status_code, 400)

    def test_api_count(self):
        # query string
        query = '{"transport/available_transportation_types_to_referral_facil'\
                'ity":"none"}'
        data = {'query': query, 'count': 1}
        response = self.client.get(self.api_url, data)
        self.assertEqual(response.status_code, 200)
        find_d = json.loads(response.content)[0]
        self.assertTrue('count' in find_d)

        data['fields'] = '["_id"]'
        response = self.client.get(self.api_url, data)
        self.assertEqual(response.status_code, 200)
        find_d = json.loads(response.content)[0]
        self.assertTrue('count' in find_d)
        self.assertEqual(find_d.get('count'), 1)

    def test_api_column_select(self):
        # query string
        query = '{"transport/available_transportation_types_to_referral_facil'\
                'ity":"none"}'
        columns = '["transport/available_transportation_types_to_referral_fac'\
                  'ility"]'
        data = {'query': query, 'fields': columns}
        request = self.factory.get(self.api_url, data)
        request.user = self.user
        response = api(request, self.user.username, self.xform.id_string)
        self.assertEqual(response.status_code, 200)
        find_d = json.loads(response.content)[0]
        self.assertTrue(
            'transport/available_transportation_types_to_referral_facility' in
            find_d)
        self.assertFalse('_attachments' in find_d)

    def test_api_decode_from_mongo(self):
        field = "$section1.group01.question1"
        encoded = _encode_for_mongo(field)
        self.assertEqual(encoded, (
            "%(dollar)ssection1%(dot)sgroup01%(dot)squestion1" % {
                "dollar": base64.b64encode(
                    '$'.encode('utf-8')).decode('utf-8'),
                "dot": base64.b64encode('.'.encode('utf-8')).decode('utf-8')}))
        decoded = _decode_from_mongo(encoded)
        self.assertEqual(field, decoded)

    def test_api_with_or_query(self):
        """Test that an or query is interpreted correctly since we use an
        internal or query to filter out deleted records"""
        for i in range(1, 3):
            self._submit_transport_instance(i)
        # record 0: does NOT have the 'transport/loop_over_transport_types_freq
        #           uency/ambulance/frequency_to_referral_facility' field
        # record 1: 'transport/loop_over_transport_types_frequency/ambulance/fr
        #           equency_to_referral_facility': 'daily'
        # record 2: 'transport/loop_over_transport_types_frequency/ambulance/fr
        #           equency_to_referral_facility': 'weekly'
        params = {
            'query':
            '{"$or": [{"transport/loop_over_transport_types_frequency/ambulanc'
            'e/frequency_to_referral_facility": "weekly"}, {"transport/loop_ov'
            'er_transport_types_frequency/ambulance/frequency_to_referral_faci'
            'lity": "daily"}]}'}
        response = self.client.get(self.api_url, params)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 2)

        # check with fields filter
        params['fields'] = '["_id"]'
        response = self.client.get(self.api_url, params)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 2)

        # check that blank params give us all our records i.e. 3
        params = {}
        response = self.client.get(self.api_url, params)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 3)

    def test_api_cors_options(self):
        response = self.anon.options(self.api_url)
        allowed_headers = ['Accept', 'Origin', 'X-Requested-With',
                           'Authorization']
        provided_headers = [h.strip() for h in response[
            'Access-Control-Allow-Headers'].split(',')]
        self.assertListEqual(allowed_headers, provided_headers)
        self.assertEqual(response['Access-Control-Allow-Methods'], 'GET')
        self.assertEqual(response['Access-Control-Allow-Origin'], '*')
