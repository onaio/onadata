import os

from django.test import RequestFactory

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.osm_viewset import OsmViewSet
from onadata.apps.logger.models import Attachment


class TestOSM(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._login_user_and_profile()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    def test_data_retrieve_instance_osm_format(self):
        filenames = [
            'OSMWay234134797.osm',
            'OSMWay34298972.osm',
        ]
        osm_fixtures_dir = os.path.realpath(os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'osm'))
        paths = [
            os.path.join(osm_fixtures_dir, filename)
            for filename in filenames]
        xlsform_path = os.path.join(osm_fixtures_dir, 'osm.xlsx')
        combined_osm_path = os.path.join(osm_fixtures_dir, 'combined.osm')
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        submission_path = os.path.join(osm_fixtures_dir, 'instance_a.xml')
        files = [open(path) for path in paths]
        count = Attachment.objects.filter(extension='osm').count()
        self._make_submission(submission_path, media_file=files)
        self.assertTrue(
            Attachment.objects.filter(extension='osm').count() > count)

        formid = self.xform.pk
        dataid = self.xform.instances.latest('date_created').pk
        request = self.factory.get('/')

        # look at the data/[pk]/[dataid].osm endpoint
        view = OsmViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid, format='osm')
        self.assertEqual(response.status_code, 200)
        with open(combined_osm_path) as f:
            osm = f.read()
            response.render()
            self.assertMultiLineEqual(response.content, osm)

            # look at the data/[pk].osm endpoint
            # view = OsmViewSet.as_view({'get': 'list'})
            response = view(request, pk=formid, format='osm')
            self.assertEqual(response.status_code, 200)
            response.render()
            self.assertMultiLineEqual(response.content, osm)

        # look at the data.osm endpoint
        view = OsmViewSet.as_view({'get': 'list'})
        response = view(request, format='osm')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'],
                         'http://testserver/api/v1/osm.json')

        response = view(request)
        self.assertEqual(response.status_code, 200)
        data = [{
            'url': 'http://testserver/api/v1/osm/{}'.format(self.xform.pk),
            'title': self.xform.title,
            'id_string': self.xform.id_string, 'user': self.xform.user.username
        }]
        self.assertEqual(response.data, data)
