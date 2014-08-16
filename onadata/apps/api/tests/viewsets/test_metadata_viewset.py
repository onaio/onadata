import os

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile

from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet)
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.main.models.meta_data import MetaData


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

    def test_add_metadata_with_file_attachment(self):
        for data_type in ['supporting_doc', 'media', 'source']:
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)

    def test_get_metadata_with_file_attachment(self):
        for data_type in ['supporting_doc', 'media', 'source']:
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)
            request = self.factory.get('/', **self.extra)
            response = self.view(request, pk=self.metadata.pk)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.metadata_data)
            ext = self.data_value[self.data_value.rindex('.') + 1:]
            request = self.factory.get('/', **self.extra)
            response = self.view(request, pk=self.metadata.pk, format=ext)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content_type, 'image/png')

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
            self._post_form_metadata(data)
            self.assertEqual(self.metadata.data_file_type, 'text/csv')

    def test_add_media_url(self):
        data_type = 'media'
        data_value = 'https://devtrac.ona.io/fieldtrips.csv'
        self._add_form_metadata(self.xform, data_type, data_value)

    def test_add_invalid_media_url(self):
        data = {
            'data_value': 'httptracfieldtrips.csv',
            'data_type': 'media',
            'xform': self.xform.pk
        }
        response = self._post_form_metadata(data, False)
        self.assertEqual(response.status_code, 400)
        error = {"data_value": ["Invalid url %s." % data['data_value']]}
        self.assertEqual(response.data, error)

    def test_invalid_post(self):
        response = self._post_form_metadata({}, False)
        self.assertEqual(response.status_code, 400)
        response = self._post_form_metadata({
            'data_type': 'supporting_doc'}, False)
        self.assertEqual(response.status_code, 400)
        response = self._post_form_metadata({
            'data_type': 'supporting_doc',
            'xform': self.xform.pk
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
        self.assertEqual(response.status_code, 200)

        data['xform'] = 1234509909
        request = self.factory.get('/', data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 404)

        data['xform'] = "INVALID"
        request = self.factory.get('/', data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
