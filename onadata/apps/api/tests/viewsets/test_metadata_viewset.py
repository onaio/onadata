import os

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import InMemoryUploadedFile

from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet)
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.serializers.xform_serializer import XFormSerializer


class TestMetaDataViewSet(TestAbstractViewSet):

    def setUp(self):
        super(TestMetaDataViewSet, self).setUp()
        self.view = MetaDataViewSet.as_view({
            'delete': 'destroy',
            'get': 'retrieve',
            'post': 'create'
        })
        self._publish_xls_form_to_project()
        self.data_value = "screenshot.png"
        self.fixture_dir = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation"
        )
        self.path = os.path.join(self.fixture_dir, self.data_value)

        ContentType.objects.get_or_create(app_label="logger", model="project")

    def _add_project_metadata(self, project, data_type, data_value, path=None):
        data = {
            'data_type': data_type,
            'data_value': data_value,
            'project': project.id
        }

        if path and data_value:
            with open(path) as media_file:
                data.update({
                    'data_file': media_file,
                })
                self._post_metadata(data)
        else:
            self._post_metadata(data)

    def test_add_metadata_with_file_attachment(self):
        for data_type in ['supporting_doc', 'media', 'source']:
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)

    def test_parse_error_is_raised(self):
        """Parse error is raised when duplicate media is uploaded"""
        data_type = "supporting_doc"

        self._add_form_metadata(self.xform, data_type,
                                self.data_value, self.path)
        # Duplicate upload
        response = self._add_form_metadata(self.xform, data_type,
                                           self.data_value, self.path, False)
        self.assertEquals(response.status_code, 400)
        self.assertIn("duplicate key", response.data['detail'])

    def test_forms_endpoint_with_metadata(self):
        date_modified = self.xform.date_modified
        for data_type in ['supporting_doc', 'media', 'source']:
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)
            self.xform.reload()
            self.assertNotEqual(date_modified, self.xform.date_modified)

        # /forms
        view = XFormViewSet.as_view({
            'get': 'retrieve'
        })
        formid = self.xform.pk
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        data = XFormSerializer(self.xform, context={'request': request}).data
        self.assertEqual(response.data, data)

        # /projects/[pk]/forms
        view = ProjectViewSet.as_view({
            'get': 'forms'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [data])

    def test_get_metadata_with_file_attachment(self):
        for data_type in ['supporting_doc', 'media', 'source']:
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)
            request = self.factory.get('/', **self.extra)
            response = self.view(request, pk=self.metadata.pk)
            self.assertNotEqual(response.get('Cache-Control'), None)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.metadata_data)
            ext = self.data_value[self.data_value.rindex('.') + 1:]
            request = self.factory.get('/', **self.extra)
            response = self.view(request, pk=self.metadata.pk, format=ext)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/png')

    def test_get_metadata(self):
        self.fixture_dir = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "instances", "transport_2011-07-25_19-05-49"
        )
        self.data_value = '1335783522563.jpg'
        self.path = os.path.join(self.fixture_dir, self.data_value)

        self._add_form_metadata(
            self.xform, "media", self.data_value, self.path)
        data = {
            'id': self.metadata.pk,
            'xform': self.xform.pk,
            'data_value': u'1335783522563.jpg',
            'data_type': u'media',
            'data_file': u'http://localhost:8000/media/%s/formid-media/'
            '1335783522563.jpg' % self.user.username,
            'data_file_type': u'image/jpeg',
            'media_url': u'http://localhost:8000/media/%s/formid-media/'
            '1335783522563.jpg' % self.user.username,
            'file_hash': u'md5:2ca0d22073a9b6b4ebe51368b08da60c',
            'url': 'http://testserver/api/v1/metadata/%s' % self.metadata.pk,
            'date_created': self.metadata.date_created
        }
        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.metadata.pk)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(dict(response.data), data)

    def test_add_mapbox_layer(self):
        data_type = 'mapbox_layer'
        data_value = 'test_mapbox_layer||http://0.0.0.0:8080||attribution'
        self._add_form_metadata(self.xform, data_type, data_value)

    def test_delete_metadata(self):
        for data_type in ['supporting_doc', 'media', 'source']:
            count = MetaData.objects.count()
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)
            request = self.factory.delete('/', **self.extra)
            response = self.view(request, pk=self.metadata.pk)
            self.assertEqual(response.status_code, 204)
            self.assertEqual(count, MetaData.objects.count())

    def test_windows_csv_file_upload_to_metadata(self):
        data_value = 'transportation.csv'
        path = os.path.join(self.fixture_dir, data_value)
        with open(path) as f:
            f = InMemoryUploadedFile(
                f, 'media', data_value, 'application/octet-stream', 2625, None)
            data = {
                'data_value': data_value,
                'data_file': f,
                'data_type': 'media',
                'xform': self.xform.pk
            }
            self._post_metadata(data)
            self.assertEqual(self.metadata.data_file_type, 'text/csv')

    def test_add_media_url(self):
        data_type = 'media'
        data_value = 'https://devtrac.ona.io/fieldtrips.csv'
        self._add_form_metadata(self.xform, data_type, data_value)
        request = self.factory.get('/', **self.extra)
        ext = self.data_value[self.data_value.rindex('.') + 1:]
        response = self.view(request, pk=self.metadata.pk, format=ext)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], data_value)

    def test_add_invalid_media_url(self):
        data = {
            'data_value': 'httptracfieldtrips.csv',
            'data_type': 'media',
            'xform': self.xform.pk
        }
        response = self._post_metadata(data, False)
        self.assertEqual(response.status_code, 400)
        error = {"data_value": ["Invalid url %s." % data['data_value']]}
        self.assertEqual(response.data, error)

    def test_invalid_post(self):
        response = self._post_metadata({}, False)
        self.assertEqual(response.status_code, 400)
        response = self._post_metadata({
            'data_type': 'supporting_doc'}, False)
        self.assertEqual(response.status_code, 400)
        response = self._post_metadata({
            'data_type': 'supporting_doc',
            'xform': self.xform.pk
        }, False)
        self.assertEqual(response.status_code, 400)
        response = self._post_metadata({
            'data_type': 'supporting_doc',
            'data_value': 'supporting.doc'
        }, False)
        self.assertEqual(response.status_code, 400)

    def _add_test_metadata(self):
        for data_type in ['supporting_doc', 'media', 'source']:
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)

    def test_list_metadata(self):
        self._add_test_metadata()
        self.view = MetaDataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)

    def test_list_metadata_for_specific_form(self):
        self._add_test_metadata()
        self.view = MetaDataViewSet.as_view({'get': 'list'})
        data = {'xform': self.xform.pk}
        request = self.factory.get('/', data)
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.get('/', data, **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)

        data['xform'] = 1234509909
        request = self.factory.get('/', data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 404)

        data['xform'] = "INVALID"
        request = self.factory.get('/', data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)

    def test_project_metadata_has_project_field(self):
        self._add_project_metadata(
            self.project, 'supporting_doc', self.data_value, self.path)

        # Test json of project metadata
        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=self.metadata_data['id'])

        self.assertEqual(response.status_code, 200)

        data = dict(response.data)

        self.assertIsNotNone(data['media_url'])
        self.assertEqual(data['project'], self.metadata.object_id)

    def test_should_return_both_xform_and_project_metadata(self):
        # delete all existing metadata
        MetaData.objects.all().delete()
        expected_metadata_count = 2

        self._add_project_metadata(
            self.project, 'media', "check.png", self.path)

        self._add_form_metadata(
            self.xform, 'supporting_doc', "bla.png", self.path)

        view = MetaDataViewSet.as_view({'get': 'list'})
        request = self.factory.get("/", **self.extra)
        response = view(request)

        self.assertEquals(MetaData.objects.count(), expected_metadata_count)

        for record in response.data:
            if record.get("xform"):
                self.assertEquals(record.get('xform'), self.xform.id)
                self.assertIsNone(record.get('project'))
            else:
                self.assertEquals(record.get('project'), self.project.id)
                self.assertIsNone(record.get('xform'))

    def test_should_only_return_xform_metadata(self):
        # delete all existing metadata
        MetaData.objects.all().delete()

        self._add_project_metadata(
            self.project, 'media', "check.png", self.path)

        self._add_form_metadata(
            self.xform, 'supporting_doc', "bla.png", self.path)

        view = MetaDataViewSet.as_view({'get': 'list'})
        query_data = {"xform": self.xform.id}
        request = self.factory.get("/", data=query_data, **self.extra)
        response = view(request)

        self.assertEqual(len(response.data), 1)
        self.assertIn("xform", response.data[0])
        self.assertNotIn("project", response.data[0])

    def _create_metadata_object(self):
        view = MetaDataViewSet.as_view({'post': 'create'})
        with open(self.path) as media_file:
            data = {
                'data_type': 'media',
                'data_value': 'check.png',
                'data_file': media_file,
                'project': self.project.id
            }
            request = self.factory.post('/', data, **self.extra)
            response = view(request)

            return response

    def test_integrity_error_is_handled(self):
        count = MetaData.objects.count()

        response = self._create_metadata_object()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(count + 1, MetaData.objects.count())

        response = self._create_metadata_object()
        self.assertEqual(response.status_code, 400)
