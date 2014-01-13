from django.core.urlresolvers import reverse
from rest_framework.test import APIClient
from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.api.views.chart_views import ChartDetail


class TestChartsView(TestBase):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.api_client = APIClient()
        self.api_client.login(username=self.login_username, password=self.login_password)
        self._publish_transportation_form()
        self.view = ChartDetail.as_view()
        self.request_factory = APIRequestFactory()

    def test_get_on_categorized_field(self):
        request = self.request_factory.get('/charts')
        force_authenticate(request, user=self.user)
        response = self.view(request, formid=self.xform.id, field_name='frequency_to_referral_facility')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['field_type'], 'select one')
        self.assertEqual(response.data['field_name'], 'frequency_to_referral_facility')
        self.assertEqual(response.data['data_type'], 'categorized')

    def test_get_on_date_field(self):
        request = self.request_factory.get('/charts')
        force_authenticate(request, user=self.user)
        response = self.view(request, formid=self.xform.id, field_name='frequency_to_referral_facility')
        self.assertEqual(response.status_code, 200)

    def test_get_on_numeric_field(self):
        pass
