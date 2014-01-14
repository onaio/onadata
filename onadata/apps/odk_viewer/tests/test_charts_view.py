from django.core.urlresolvers import reverse
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.odk_viewer.views import charts


class TestChartsView(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        self._publish_transportation_form_and_submit_instance()
        self.url = reverse(charts, kwargs={
            'username': self.user.username,
            'id_string': self.xform.id_string
        })

    def test_charts_view_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)