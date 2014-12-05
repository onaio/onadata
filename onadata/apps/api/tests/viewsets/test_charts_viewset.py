import os

from rest_framework.test import APIClient
from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate
from onadata.apps.api.viewsets.charts_viewset import ChartsViewSet
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models.instance import Instance


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
        self.assertEqual(_dict.get('_duration'), 24.898)
        self.assertNotEqual(_dict.get('_duration'), None)

        # the instance below has a valid start time and an invalid end time
        instance = Instance.objects.all()[1]
        _dict = instance.parsed_instance.to_dict_for_mongo()
        self.assertIn('_duration', _dict.keys())
        self.assertEqual(_dict.get('_duration'), '')
        self.assertNotEqual(_dict.get('_duration'), None)

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
        self.assertEqual(response.status_text, u'BAD REQUEST')

    def test_get_on_date_field(self):
        data = {'field_name': 'date'}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['field_type'], 'date')
        self.assertEqual(response.data['field_name'], 'date')
        self.assertEqual(response.data['data_type'], 'time_based')

    def test_get_on_numeric_field(self):
        data = {'field_name': 'age'}
        request = self.factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id
        )
        self.assertEqual(response.status_code, 200)
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
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        data = {'id': self.xform.pk, 'id_string': self.xform.id_string,
                'url': 'http://testserver/api/v1/charts/%s' % self.xform.pk}
        self.assertEqual(response.data, [data])

        request = self.factory.get('/charts')
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
