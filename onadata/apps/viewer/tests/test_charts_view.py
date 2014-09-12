import os
from django.core.urlresolvers import reverse
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.views import charts


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

    def test_chart_view_with_lang_param(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "main", "tests", "fixtures",
                            "good_eats_multilang", "good_eats_multilang.xls")
        self._publish_xls_file_and_set_xform(path)
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "main", "tests", "fixtures",
                            "good_eats_multilang", "1.xml")
        self._make_submission(path)

        params = {
            'lang': 0
        }
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)

    def test_chart_view_with_bad_lang_param(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "main", "tests", "fixtures",
                            "good_eats_multilang", "good_eats_multilang.xls")
        self._publish_xls_file_and_set_xform(path)
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "main", "tests", "fixtures",
                            "good_eats_multilang", "1.xml")
        self._make_submission(path)

        params = {
            'lang': "-"
        }
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
