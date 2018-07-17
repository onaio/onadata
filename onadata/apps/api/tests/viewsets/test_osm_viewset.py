import csv
import os
from io import StringIO

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.transaction import TransactionManagementError
from django.test import RequestFactory
from django.test.utils import override_settings
from django.utils.dateparse import parse_datetime

from mock import patch

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.api.viewsets.osm_viewset import OsmViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import Attachment, Instance, OsmData
from onadata.apps.viewer.models import Export
from onadata.libs.utils.common_tools import (filename_from_disposition,
                                             get_response_content)
from onadata.libs.utils.osm import save_osm_data


class TestOSMViewSet(TestAbstractViewSet):

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

        # look at the forms.json?instances_with_osm=True
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

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
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
            self.assertMultiLineEqual(response.content.decode('utf-8').strip(),
                                      osm.strip())

            # look at the data/[pk].osm endpoint
            view = OsmViewSet.as_view({'get': 'list'})
            response = view(request, pk=formid, format='osm')
            self.assertEqual(response.status_code, 200)
            response.render()
            self.assertMultiLineEqual(response.content.decode('utf-8').strip(),
                                      osm.strip())

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

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_osm_csv_export(self):
        self._publish_osm_with_submission()
        count = Export.objects.all().count()

        view = XFormViewSet.as_view({
            'get': 'retrieve'
        })

        request = self.factory.get('/', data={'include_images': False},
                                   **self.extra)
        response = view(request, pk=self.xform.pk, format='csv')
        self.assertEqual(response.status_code, 200)

        self.assertEquals(count + 1, Export.objects.all().count())

        headers = dict(response.items())
        self.assertEqual(headers['Content-Type'], 'application/csv')
        content_disposition = headers['Content-Disposition']
        filename = filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(ext, '.csv')

        content = get_response_content(response)
        reader = csv.DictReader(StringIO(content))
        data = [_ for _ in reader]
        test_file_path = os.path.join(self.fixtures_dir, 'osm.csv')
        with open(test_file_path, 'r') as test_file:
            expected_csv_reader = csv.DictReader(test_file)
            for index, row in enumerate(expected_csv_reader):
                self.assertDictContainsSubset(row, data[index])

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.xform.pk, format='csv')
        self.assertEqual(response.status_code, 200)

    def test_process_error_osm_format(self):
        self._publish_xls_form_to_project()
        self._make_submissions()
        request = self.factory.get('/')
        view = DataViewSet.as_view({'get': 'retrieve'})
        dataid = self.xform.instances.all().order_by('id')[0].pk
        response = view(request, pk=self.xform.pk, dataid=dataid, format='osm')
        self.assertContains(response, '<error>Not found.</error>',
                            status_code=404)

    def test_save_osm_data_transaction_atomic(self):
        """
        Test that an IntegrityError within save_osm_data does not cause
        a TransactionManagementError, which arises because of new queries
        while inside a transaction.atomic() block
        """

        # first publish a form and make a submission with OSM data
        self._publish_osm_with_submission()
        # make sure we have a submission
        submission = Instance.objects.first()
        self.assertNotEqual(submission, None)

        # mock the save method on OsmData and cause it to raise an
        # IntegrityError on its first call only, so that we get into the
        # catch inside save_osm_data
        with patch('onadata.libs.utils.osm.OsmData.save') as mock:

            def _side_effect(*args):
                """
                We want to raise an IntegrityError only on the first call
                of our mock
                """

                def __second_side_effect(*args):
                    return None

                # change the side effect so that the next time we do not
                # raise an IntegrityError
                mock.side_effect = __second_side_effect
                # we need to manually rollback the atomic transaction
                # merely raising IntegrityError is not enough
                # doing this means that a TransactionManagementError is raised
                # if we do new queries inside the transaction.atomic block
                transaction.set_rollback(True)
                raise IntegrityError

            # excplicity use an atomic block
            with transaction.atomic():
                mock.side_effect = _side_effect
                try:
                    save_osm_data(submission.id)
                except TransactionManagementError:
                    self.fail("TransactionManagementError was raised")

    def test_save_osm_data_with_non_existing_media_file(self):
        """
        Test that saving osm data with a non existing media file
        fails silenty and does not throw an IOError
        """
        osm_fixtures_dir = os.path.realpath(os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'osm'))

        # publish form
        xlsform_path = os.path.join(osm_fixtures_dir, 'osm.xlsx')
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.xform.save()
        # make submission with osm data
        submission_path = os.path.join(osm_fixtures_dir, 'instance_a.xml')
        media_file = open(os.path.join(osm_fixtures_dir,
                          'OSMWay234134797.osm'))
        self._make_submission(submission_path, media_file=media_file)
        # save osm data with a non existing file
        submission = Instance.objects.first()
        attachment = submission.attachments.first()
        attachment.media_file = os.path.join(
            settings.PROJECT_ROOT, "test_media", "noFile.osm")
        attachment.save()
        try:
            save_osm_data(submission.id)
        except IOError:
            self.fail("IOError was raised")
