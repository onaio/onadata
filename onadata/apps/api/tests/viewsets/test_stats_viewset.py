import os

from django.core.files.base import ContentFile
from django.test import RequestFactory
from mock import patch

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.api.viewsets.stats_viewset import StatsViewSet
from onadata.apps.api.viewsets.submissionstats_viewset import\
    SubmissionStatsViewSet
from onadata.apps.logger.models import XForm
from onadata.libs.utils.logger_tools import publish_xml_form, create_instance


class TestStatsViewSet(TestBase):

    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    @patch('onadata.apps.logger.models.instance.submission_time')
    def test_form_list(self, mock_time):
        self._set_mock_time(mock_time)
        self._publish_transportation_form()
        self._make_submissions()
        view = SubmissionStatsViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = {
            u'transportation_2011_07_25':
            'http://testserver/api/v1/stats/submissions/bob/%s' % formid
        }
        self.assertDictEqual(response.data, data)
        request = self.factory.get('/?group=_xform_id_string', **self.extra)
        response = view(request)
        response = view(request, owner='bob', formid=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        data = {
            u'count': 4
        }
        self.assertDictContainsSubset(data, response.data[0])

    def test_anon_form_list(self):
        self._publish_transportation_form()
        self._make_submissions()
        view = SubmissionStatsViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        response = view(request)
        self.assertEqual(response.status_code, 401)

    def _contributions_form_submissions(self):
        count = XForm.objects.count()
        path = os.path.join(os.path.dirname(__file__),
                            '..', 'fixtures', 'forms', 'contributions')
        form_path = os.path.join(path, 'contributions.xml')
        f = open(form_path)
        xml_file = ContentFile(f.read())
        f.close()
        xml_file.name = 'contributions.xml'
        self.xform = publish_xml_form(xml_file, self.user)
        self.assertTrue(XForm.objects.count() > count)
        instances_path = os.path.join(path, 'instances')
        for uuid in os.listdir(instances_path):
            s_path = os.path.join(instances_path, uuid, 'submission.xml')
            create_instance(self.user.username, open(s_path), [])
        self.assertEqual(self.xform.instances.count(), 6)

    def test_median_api(self):
        self._contributions_form_submissions()
        view = StatsViewSet.as_view({'get': 'list'})
        request = self.factory.get('/?method=median', **self.extra)
        formid = self.xform.pk
        response = view(request, owner='bob', formid=formid)
        data = {u'age': 28.5, u'amount': 1100.0}
        self.assertDictContainsSubset(data, response.data)

    def test_mean_api(self):
        self._contributions_form_submissions()
        view = StatsViewSet.as_view({'get': 'list'})
        request = self.factory.get('/?method=mean', **self.extra)
        formid = self.xform.pk
        response = view(request, owner='bob', formid=formid)
        data = {u'age': 28.17, u'amount': 1455.0}
        self.assertDictContainsSubset(data, response.data)

    def test_mode_api(self):
        self._contributions_form_submissions()
        view = StatsViewSet.as_view({'get': 'list'})
        request = self.factory.get('/?method=mode', **self.extra)
        formid = self.xform.pk
        response = view(request, owner='bob', formid=formid)
        data = {u'age': 24, u'amount': 430.0}
        self.assertDictContainsSubset(data, response.data)

    def test_range_api(self):
        self._contributions_form_submissions()
        view = StatsViewSet.as_view({'get': 'list'})
        request = self.factory.get('/?method=range', **self.extra)
        formid = self.xform.pk
        response = view(request, owner='bob', formid=formid)
        data = {u'age': {u'range': 10, u'max': 34, u'min': 24},
                u'amount': {u'range': 2770, u'max': 3200, u'min': 430}}
        self.assertDictContainsSubset(data, response.data)

    def test_all_stats_api(self):
        self._contributions_form_submissions()
        view = StatsViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = {
            u'contributions':
            'http://testserver/api/v1/stats/bob/%s' % formid
        }
        self.assertDictContainsSubset(data, response.data)
        response = view(request, owner='bob', formid=formid)
        data = {}
        data['age'] = {
            'mean': 28.17,
            'median': 28.5,
            'mode': 24,
            'max': 34,
            'min': 24,
            'range': 10
        }
        request = self.factory.get('/?field=age', **self.extra)
        age_response = view(request, owner='bob', formid=formid)
        self.assertEqual(data, age_response.data)
        data['amount'] = {
            'mean': 1455,
            'median': 1100.0,
            'mode': 430,
            'max': 3200,
            'min': 430,
            'range': 2770
        }
        self.assertDictContainsSubset(data, response.data)
