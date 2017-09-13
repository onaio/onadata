import os
import mock

from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate
from onadata.apps.api.viewsets.charts_viewset import ChartsViewSet
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models.instance import Instance
from django.db.utils import DataError
from onadata.libs.utils.timing import calculate_duration
from onadata.libs.renderers.renderers import DecimalJSONRenderer


def raise_data_error(a):
    raise DataError


class TestChartsViewSet(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        # publish tutorial form as it has all the different field types
        self._publish_xls_file_and_set_xform(
            os.path.join(
                os.path.dirname(__file__),
                '..', 'fixtures', 'forms', 'tutorial', 'tutorial.xls'))
        self.api_client = APIClient()
        self.api_client.login(
            username=self.login_username, password=self.login_password)
        self.view = ChartsViewSet.as_view({
            'get': 'retrieve'
        })
        self.factory = APIRequestFactory()
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__), '..', 'fixtures', 'forms',
                'tutorial', 'instances', '1.xml'))
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__), '..', 'fixtures', 'forms',
                'tutorial', 'instances', '2.xml'))
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__), '..', 'fixtures', 'forms',
                'tutorial', 'instances', '3.xml'))

    def test_duration_field_on_metadata(self):
        # the instance below has valid start and end times
        instance = Instance.objects.all()[0]
        _dict = instance.parsed_instance.to_dict_for_mongo()
        self.assertIn('_duration', _dict.keys())
        self.assertEqual(_dict.get('_duration'), 24.0)
        self.assertNotEqual(_dict.get('_duration'), None)

        _dict = instance.json
        duration = calculate_duration(_dict.get('start_time'), 'invalid')
        self.assertIn('_duration', _dict.keys())
        self.assertEqual(duration, '')
        self.assertNotEqual(duration, None)

    def test_get_on_categorized_field(self):
        data = {'field_name': 'gender'}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id,
            format='html'
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'select one')
        self.assertEqual(response.data['field_name'], 'gender')
        self.assertEqual(response.data['data_type'], 'categorized')
        self.assertEqual(response.data['data'][0]['gender'], 'Male')
        self.assertEqual(response.data['data'][1]['gender'], 'Female')

    def test_return_bad_request_on_non_json_request_with_field_name(self):
        request = self.factory.get('/charts/%s.html' % self.xform.id)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.status_text.upper(), u'BAD REQUEST')

    def test_get_on_date_field(self):
        data = {'field_name': 'date'}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'date')
        self.assertEqual(response.data['field_name'], 'date')
        self.assertEqual(response.data['data_type'], 'time_based')

    @mock.patch('onadata.libs.data.query._execute_query',
                side_effect=raise_data_error)
    def test_get_on_date_field_with_invalid_data(self, mock_execute_query):
        data = {'field_name': 'date'}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id)
        self.assertEqual(response.status_code, 400)

    def test_get_on_numeric_field(self):
        data = {'field_name': 'age'}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'integer')
        self.assertEqual(response.data['field_name'], 'age')
        self.assertEqual(response.data['data_type'], 'numeric')

    def test_get_on_select_field(self):
        data = {'field_name': 'gender'}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'select one')
        self.assertEqual(response.data['field_name'], 'gender')
        self.assertEqual(response.data['data_type'], 'categorized')

    def test_get_on_select_field_xpath(self):
        data = {'field_xpath': 'gender'}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'select one')
        self.assertEqual(response.data['field_name'], 'gender')
        self.assertEqual(response.data['data_type'], 'categorized')

    def test_get_on_select_multi_field(self):
        field_name = 'favorite_toppings'
        data = {'field_name': field_name}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'select all that apply')
        self.assertEqual(response.data['field_name'], field_name)
        self.assertEqual(response.data['data_type'], 'categorized')

        options = response.data['data'][0][field_name]
        self.assertEqual(options, ['Green Peppers', 'Pepperoni'])

    def test_get_on_select_multi_field_html_format(self):
        field_name = 'favorite_toppings'
        data = {'field_name': field_name}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id,
            format='html'
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'select all that apply')
        self.assertEqual(response.data['field_name'], field_name)
        self.assertEqual(response.data['data_type'], 'categorized')

        options = response.data['data'][0][field_name]
        self.assertEqual(options, 'Green Peppers, Pepperoni')

    def test_get_all_fields(self):
        data = {'fields': 'all'}
        request = self.factory.get('/', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertIn('age', response.data)
        self.assertIn('date', response.data)
        self.assertIn('gender', response.data)
        self.assertEqual(response.data['age']['field_type'], 'integer')
        self.assertEqual(response.data['age']['field_name'], 'age')
        self.assertEqual(response.data['age']['data_type'], 'numeric')

    def test_get_specific_fields(self):
        data = {'fields': 'date,age'}
        request = self.factory.get('/', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)

        self.assertNotIn('gender', response.data)

        self.assertIn('age', response.data)
        data = response.data['age']
        self.assertEqual(data['field_type'], 'integer')
        self.assertEqual(data['field_name'], 'age')
        self.assertEqual(data['data_type'], 'numeric')

        self.assertIn('date', response.data)
        data = response.data['date']
        self.assertEqual(data['field_type'], 'date')
        self.assertEqual(data['field_name'], 'date')
        self.assertEqual(data['data_type'], 'time_based')

    def test_get_invalid_field_name(self):
        data = {'fields': 'invalid_field_name'}
        request = self.factory.get('/', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id
        )
        self.assertEqual(response.status_code, 404)

    def test_chart_list(self):
        self.view = ChartsViewSet.as_view({
            'get': 'list'
        })
        request = self.factory.get('/charts')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        data = {'id': self.xform.pk, 'id_string': self.xform.id_string,
                'url': 'http://testserver/api/v1/charts/%s' % self.xform.pk}
        self.assertEqual(response.data, [data])

        request = self.factory.get('/charts')
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_chart_list_with_xform_in_delete_async(self):
        self.view = ChartsViewSet.as_view({
            'get': 'list'
        })
        request = self.factory.get('/charts')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        data = {'id': self.xform.pk, 'id_string': self.xform.id_string,
                'url': 'http://testserver/api/v1/charts/%s' % self.xform.pk}
        self.assertEqual(response.data, [data])

        self.xform.deleted_at = timezone.now()
        self.xform.save()
        request = self.factory.get('/charts')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_cascading_select(self):
        # publish tutorial form as it has all the different field types
        self._publish_xls_file_and_set_xform(
            os.path.join(
                os.path.dirname(__file__),
                '..', 'fixtures', 'forms', 'cascading', 'cascading.xlsx'))

        self._make_submission(
            os.path.join(
                os.path.dirname(__file__), '..', 'fixtures', 'forms',
                'cascading', 'instances', '1.xml'))
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__), '..', 'fixtures', 'forms',
                'cascading', 'instances', '2.xml'))
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__), '..', 'fixtures', 'forms',
                'cascading', 'instances', '3.xml'))
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__), '..', 'fixtures', 'forms',
                'cascading', 'instances', '4.xml'))

        data = {'field_name': 'cities'}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id,
            format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data)
        expected = [
            {'cities': [u'Nice'], 'count': 1},
            {'cities': [u'Seoul'], 'count': 1},
            {'cities': [u'Cape Town'], 'count': 2}
        ]
        self.assertEqual(expected, response.data['data'])

    def test_deleted_submission_not_in_chart_endpoint(self):
        data = {'field_name': 'gender'}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id,
            format='html'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sum([i['count'] for i in response.data['data']]), 3)

        # soft delete one instance

        inst = self.xform.instances.all()[0]
        inst.set_deleted(timezone.now())

        response = self.view(
            request,
            pk=self.xform.id,
            format='html'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sum([i['count'] for i in response.data['data']]), 2)

    def test_nan_not_json_response(self):
        self._make_submission(
            os.path.join(
                os.path.dirname(__file__), '..', 'fixtures', 'forms',
                'tutorial', 'instances', 'nan_net_worth.xml'))

        data = {'field_name': 'networth_calc',
                'group_by': 'pizza_fan'}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id,
            format='json'
        )
        renderer = DecimalJSONRenderer()
        res = renderer.render(response.data)

        expected = ('{"field_type":"calculate","data_type":"numeric",'
                    '"field_xpath":"networth_calc","data":[{"count":2,'
                    '"sum":150000.0,'
                    '"pizza_fan":["No"],"mean":75000.0},{"count":2,"sum":null,'
                    '"pizza_fan":["Yes"],"mean":null}],"grouped_by":'
                    '"pizza_fan","field_label":"Networth Calc","field_name":'
                    '"networth_calc","xform":' + str(self.xform.pk) + '}')
        self.assertEqual(expected, res)
