from onadata.apps.main.tests.test_base import TestBase
from django.test.client import RequestFactory
from onadata.apps.viewer.views import stats_tables


class TestStatsTableView(TestBase):
    def setUp(self):
        super(TestStatsTableView, self).setUp()
        # Every test needs access to the request factory.
        self.factory = RequestFactory()
        self._publish_transportation_form_and_submit_instance()

    def test_view_returns_200(self):
        request = self.factory.get(
            '/{}/forms/{}/tables'.format(
                self.user.username, self.xform.id_string))

        request.user = self.user
        response = stats_tables(
            request, self.user.username, self.xform.id_string)
        self.assertEqual(response.status_code, 200)
