import os

from rest_framework.test import APIClient
from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.api.views.chart_views import ChartDetail


class TestChartsView(TestBase):
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
        self.view = ChartDetail.as_view()
        self.request_factory = APIRequestFactory()

    def test_get_on_categorized_field(self):
        request = self.request_factory.get('/charts')
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            formid=self.xform.id,
            field_name='gender')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['field_type'], 'select one')
        self.assertEqual(response.data['field_name'], 'gender')
        self.assertEqual(response.data['data_type'], 'categorized')

    def test_get_on_date_field(self):
        request = self.request_factory.get('/charts')
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            formid=self.xform.id,
            field_name='date')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['field_type'], 'date')
        self.assertEqual(response.data['field_name'], 'date')
        self.assertEqual(response.data['data_type'], 'time_based')

    def test_get_on_numeric_field(self):
        request = self.request_factory.get('/charts')
        force_authenticate(request, user=self.user)
        response = self.view(
            request,
            formid=self.xform.id,
            field_name='age')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['field_type'], 'integer')
        self.assertEqual(response.data['field_name'], 'age')
        self.assertEqual(response.data['data_type'], 'numeric')
