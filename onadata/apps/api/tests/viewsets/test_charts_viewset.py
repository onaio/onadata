import os

from rest_framework.test import APIClient
from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.api.viewsets.charts_viewset import ChartsViewSet


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
        self.request_factory = APIRequestFactory()

    def test_get_on_categorized_field(self):
        data = {'field_name': 'gender'}
        request = self.request_factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['field_type'], 'select one')
        self.assertEqual(response.data['field_name'], 'gender')
        self.assertEqual(response.data['data_type'], 'categorized')

    def test_return_bad_request_on_non_json_request_with_field_name(self):
        request = self.request_factory.get('/charts/%s.html' % self.xform.id)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.status_text, u'BAD REQUEST')

    def test_get_on_date_field(self):
        data = {'field_name': 'date'}
        request = self.request_factory.get('/charts', data)
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
        request = self.request_factory.get('/charts', data)
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            pk=self.xform.id
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['field_type'], 'integer')
        self.assertEqual(response.data['field_name'], 'age')
        self.assertEqual(response.data['data_type'], 'numeric')

    def test_get_all_fields(self):
        data = {'fields': 'all'}
        request = self.request_factory.get('/', data)
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
        request = self.request_factory.get('/', data)
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
        request = self.request_factory.get('/', data)
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
        request = self.request_factory.get('/charts')
        force_authenticate(request, user=self.user)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = {'id': self.xform.pk, 'id_string': self.xform.id_string,
                'url': 'http://testserver/api/v1/charts/%s' % self.xform.pk}
        self.assertEqual(response.data, [data])

        request = self.request_factory.get('/charts')
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
