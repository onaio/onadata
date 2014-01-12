from django.core.urlresolvers import reverse
from onadata.apps.main.tests.test_base import TestBase
from rest_framework.test import APIClient
from onadata.apps.api.views.chart_views import ChartDetail
from rest_framework.test import APIRequestFactory


class TestChartsView(TestBase):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.api_client = APIClient()
        self.api_client.login(username=self.login_username, password=self.login_password)
        self._publish_transportation_form()
        self.view = ChartDetail.as_view()

    def test_get_on_categorized_field(self):
        url = '/api/v1/charts/{}/frequency_to_referral_facility'.format(self.xform.id)
        response = self.api_client.get(url)
        #factory = APIRequestFactory()
        #request = factory.get(url)
        import ipdb; ipdb.set_trace()
        #response = self.view(request)
        self.assertEqual(response.status_code, 200)
        response_data = response.raw_post_data
        self.assertEqual(response_data['field_type'], 'select one')
        self.assertEqual(response_data['field_name'], 'frequency_to_referral_facility')
        self.assertEqual(response_data['data_type'], 'categorized')

    def test_get_on_date_field(self):
        factory = APIRequestFactory()
        request = factory.get('/charts')
        import ipdb; ipdb.set_trace()
        response = self.view(request, formid=self.xform.id, field_name='frequency_to_referral_facility')
        self.assertEqual(response.status_code, 200)

    def test_get_on_numeric_field(self):
        pass
