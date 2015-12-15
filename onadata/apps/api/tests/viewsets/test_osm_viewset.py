import os

from django.test import RequestFactory
from django.test.utils import override_settings
from django.utils.dateparse import parse_datetime

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet, \
    get_response_content, \
    filename_from_disposition
from onadata.apps.api.viewsets.osm_viewset import OsmViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import Attachment
from onadata.apps.logger.models import OsmData
from onadata.apps.viewer.models import Export


class TestOSM(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._login_user_and_profile()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    def _publish_osm_with_submission(self):
        filenames = [
            'OSMWay234134797.osm',
            'OSMWay34298972.osm',
        ]
        self.fixtures_dir = osm_fixtures_dir = os.path.realpath(os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'osm'))
        paths = [
            os.path.join(osm_fixtures_dir, filename)
            for filename in filenames]
        xlsform_path = os.path.join(osm_fixtures_dir, 'osm.xlsx')
        self.combined_osm_path = os.path.join(osm_fixtures_dir, 'combined.osm')
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.xform.version = '201511091147'
        self.xform.save()

        # look at the forms.json?instances_with_osm=False
        request = self.factory.get('/', {'instances_with_osm': 'True'},
                                   **self.extra)
        view = XFormViewSet.as_view({'get': 'list'})
        response = view(request, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        submission_path = os.path.join(osm_fixtures_dir, 'instance_a.xml')
        files = [open(path) for path in paths]
        count = Attachment.objects.filter(extension='osm').count()
        count_osm = OsmData.objects.count()
        _submission_time = parse_datetime('2013-02-18 15:54:01Z')
        self._make_submission(submission_path, media_file=files,
                              forced_submission_time=_submission_time)
        self.assertTrue(
            Attachment.objects.filter(extension='osm').count() > count)
        self.assertEqual(OsmData.objects.count(), count_osm + 2)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    def test_data_retrieve_instance_osm_format(self):
        self._publish_osm_with_submission()
        formid = self.xform.pk
        dataid = self.xform.instances.latest('date_created').pk
        request = self.factory.get('/')

        # look at the data/[pk]/[dataid].osm endpoint
        view = OsmViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid, format='osm')
        self.assertEqual(response.status_code, 200)
        with open(self.combined_osm_path) as f:
            osm = f.read()
            response.render()
            self.assertMultiLineEqual(response.content.strip(), osm.strip())

            # look at the data/[pk].osm endpoint
            view = OsmViewSet.as_view({'get': 'list'})
            response = view(request, pk=formid, format='osm')
            self.assertEqual(response.status_code, 200)
            response.render()
            self.assertMultiLineEqual(response.content.strip(), osm.strip())

        # look at the data.osm endpoint
        view = OsmViewSet.as_view({'get': 'list'})
        response = view(request, format='osm')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'],
                         'http://testserver/api/v1/osm.json')

        response = view(request, format='json')
        self.assertEqual(response.status_code, 200)
        data = [{
            'url': 'http://testserver/api/v1/osm/{}'.format(self.xform.pk),
            'title': self.xform.title,
            'id_string': self.xform.id_string, 'user': self.xform.user.username
        }]
        self.assertEqual(response.data, data)

        # look at the forms.json?instances_with_osm=True
        request = self.factory.get('/', {'instances_with_osm': 'True'},
                                   **self.extra)
        view = XFormViewSet.as_view({'get': 'list'})
        response = view(request, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data, [])

    @override_settings(CELERY_ALWAYS_EAGER=True)
    def test_osm_csv_export(self):
        self._publish_osm_with_submission()
        count = Export.objects.all().count()

        view = XFormViewSet.as_view({
            'get': 'retrieve'
        })

        request = self.factory.get('/', data={'include_images': True},
                                   **self.extra)
        response = view(request, pk=self.xform.pk, format='csv')
        self.assertEqual(response.status_code, 200)

        self.assertEquals(count+1, Export.objects.all().count())

        headers = dict(response.items())
        self.assertEqual(headers['Content-Type'], 'application/csv')
        content_disposition = headers['Content-Disposition']
        filename = filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(ext, '.csv')

        content = get_response_content(response)
        test_file_path = os.path.join(self.fixtures_dir, 'osm.csv')
        with open(test_file_path, 'r') as test_file:
            self.assertEqual(content, test_file.read())

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.xform.pk, format='csv')
        self.assertEqual(response.status_code, 200)
