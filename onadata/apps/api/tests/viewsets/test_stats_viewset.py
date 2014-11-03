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
    def test_submissions_stats(self, mock_time):
        self._set_mock_time(mock_time)
        self._publish_transportation_form()
        self._make_submissions()
        view = SubmissionStatsViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = [{
            'id': formid,
            'id_string': u'transportation_2011_07_25',
            'url': 'http://testserver/api/v1/stats/submissions/%s' % formid
        }]
        self.assertEqual(response.data, data)

        view = SubmissionStatsViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        data = {u'detail': u'Expecting `group` and `name` query parameters.'}
        self.assertEqual(response.data, data)

        request = self.factory.get('/?group=_xform_id_string', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        data = {
            u'count': 4
        }
        self.assertDictContainsSubset(data, response.data[0])

    def test_form_list_select_one_choices_multi_language(self):
        paths = [os.path.join(
            self.this_directory, 'fixtures', 'good_eats_multilang', x)
            for x in ['good_eats_multilang.xls', '1.xml']]
        self._publish_xls_file_and_set_xform(paths[0])
        self._make_submission(paths[1])
        view = SubmissionStatsViewSet.as_view({'get': 'retrieve'})
        formid = self.xform.pk
        request = self.factory.get('/?group=rating',
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        data = [{'count': 1, 'rating': u'Nothing Special'}]
        self.assertEqual(data, response.data)

    def test_form_list_select_one_choices(self):
        self._tutorial_form_submission()
        view = SubmissionStatsViewSet.as_view({'get': 'retrieve'})
        formid = self.xform.pk
        request = self.factory.get('/?group=gender', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        data = [
            {'count': 2, 'gender': u'Female'},
            {'count': 1, 'gender': u'Male'}
        ]
        self.assertEqual(sorted(data), sorted(response.data))

    def test_anon_form_list(self):
        self._publish_transportation_form()
        self._make_submissions()
        view = SubmissionStatsViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def _tutorial_form_submission(self):
        tutorial_folder = os.path.join(
            os.path.dirname(__file__),
            '..', 'fixtures', 'forms', 'tutorial')
        self._publish_xls_file_and_set_xform(os.path.join(tutorial_folder,
                                                          'tutorial.xls'))
        instance_paths = [os.path.join(tutorial_folder, 'instances', i)
                          for i in ['1.xml', '2.xml', '3.xml']]
        for path in instance_paths:
            create_instance(self.user.username, open(path), [])

        self.assertEqual(self.xform.instances.count(), 3)

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
        view = StatsViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/?method=median', **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)
        data = {u'age': 28.5, u'amount': 1100.0}
        self.assertDictContainsSubset(data, response.data)

    def test_mean_api(self):
        self._contributions_form_submissions()
        view = StatsViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/?method=mean', **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)
        data = {u'age': 28.17, u'amount': 1455.0}
        self.assertDictContainsSubset(data, response.data)

    def test_mode_api(self):
        self._contributions_form_submissions()
        view = StatsViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/?method=mode', **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)
        data = {u'age': 24, u'amount': 430.0}
        self.assertDictContainsSubset(data, response.data)

    def test_range_api(self):
        self._contributions_form_submissions()
        view = StatsViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/?method=range', **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)
        data = {u'age': {u'range': 10, u'max': 34, u'min': 24},
                u'amount': {u'range': 2770, u'max': 3200, u'min': 430}}
        self.assertDictContainsSubset(data, response.data)

    def test_bad_field(self):
        self._contributions_form_submissions()
        view = StatsViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/?method=median&field=INVALID',
                                   **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)

    def test_all_stats_api(self):
        self._contributions_form_submissions()
        view = StatsViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = [{
            u'id': formid,
            u'id_string': u'contributions',
            u'url': u'http://testserver/api/v1/stats/%s' % formid
        }]
        self.assertEqual(data, response.data)

        view = StatsViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid)
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
        age_response = view(request, pk=formid)
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

    def test_wrong_stat_function_api(self):
        self._contributions_form_submissions()
        view = StatsViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/?method=modes', **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)

        self.assertEquals(response.status_code, 200)
