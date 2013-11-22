from django.test import RequestFactory
from main.tests.test_base import MainTestCase

from api.views import StatsViewSet


class TestDataAPI(MainTestCase):

    def setUp(self):
        MainTestCase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form()
        self._make_submissions()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    def test_form_list(self):
        view = StatsViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = {
            u'transportation_2011_07_25':
            'http://testserver/api/v1/stats/submissions/bob/%s' % formid
        }
        self.assertDictEqual(response.data, data)
        response = view(request, owner='bob', formid=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        data = {
            u'count': 4
        }
        self.assertDictContainsSubset(data, response.data[0])
