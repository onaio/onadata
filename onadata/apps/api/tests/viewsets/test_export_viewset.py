import os

from django.conf import settings


from onadata.apps.api.viewsets.export_viewset import ExportViewSet
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export

from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status

from tempfile import NamedTemporaryFile


class TestExportViewSet(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.factory = APIRequestFactory()
        self.formats = ['csv', 'csvzip', 'kml', 'osm', 'savzip', 'xls',
                        'xlsx', 'zip']
        self.view = ExportViewSet.as_view({'get': 'retrieve'})

    def test_generates_expected_response(self):
        self._create_user_and_login()
        self._publish_transportation_form()
        temp_dir = settings.MEDIA_ROOT
        dummy_export_file = NamedTemporaryFile(suffix='.xlsx', dir=temp_dir)
        filename = os.path.basename(dummy_export_file.name)
        filedir = os.path.dirname(dummy_export_file.name)
        export = Export.objects.create(xform=self.xform,
                                       filename=filename,
                                       filedir=filedir)
        export.save()
        request = self.factory.get('/export')
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=export.pk)
        self.assertIn(filename, response.get('Content-Disposition'))

    def test_export_format_renderers_present(self):
        renderer_formats = [rc.format for rc in self.view.cls.renderer_classes]

        for f in self.formats:
            self.assertIn(f, renderer_formats)

    def test_export_non_existent_file(self):
        self._create_user_and_login()
        pk = 1525266252676
        for f in self.formats:
            request = self.factory.get('/export')
            response = self.view(request, pk=pk, format=f)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_list(self):
        view = ExportViewSet.as_view({'get': 'list'})
        request = self.factory.get('/export')
        response = view(request)
        self.assertFalse(bool(response.data))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_list_public(self):
        self._create_user_and_login()
        self._publish_transportation_form()
        self.xform.shared_data = True
        self.xform.save()
        temp_dir = settings.MEDIA_ROOT
        dummy_export_file = NamedTemporaryFile(suffix='.xlsx', dir=temp_dir)
        filename = os.path.basename(dummy_export_file.name)
        filedir = os.path.dirname(dummy_export_file.name)
        export = Export.objects.create(xform=self.xform,
                                       filename=filename,
                                       filedir=filedir)
        export.save()
        view = ExportViewSet.as_view({'get': 'list'})
        request = self.factory.get('/export')
        response = view(request)
        self.assertTrue(bool(response.data))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_list_on_user(self):
        self._create_user_and_login()
        self._publish_transportation_form()
        temp_dir = settings.MEDIA_ROOT
        dummy_export_file = NamedTemporaryFile(suffix='.xlsx', dir=temp_dir)
        filename = os.path.basename(dummy_export_file.name)
        filedir = os.path.dirname(dummy_export_file.name)
        exports = [Export.objects.create(xform=self.xform,
                                         filename=filename,
                                         filedir=filedir)]
        exports[0].save()
        view = ExportViewSet.as_view({'get': 'list'})
        request = self.factory.get('/export', data={'xform': self.xform.id})
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(len(exports), len(response.data))
        self.assertEqual(exports[0].id, response.data[0].get('id'))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_list_on_with_different_users(self):
        self._create_user_and_login()
        self._publish_transportation_form()
        temp_dir = settings.MEDIA_ROOT
        dummy_export_file = NamedTemporaryFile(suffix='.xlsx', dir=temp_dir)
        filename = os.path.basename(dummy_export_file.name)
        filedir = os.path.dirname(dummy_export_file.name)
        export = Export.objects.create(xform=self.xform,
                                       filename=filename,
                                       filedir=filedir)
        export.save()
        view = ExportViewSet.as_view({'get': 'list'})
        request = self.factory.get('/export', data={'xform': self.xform.id})
        self._create_user_and_login(username='mary', password='password1')
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertFalse(bool(response.data))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
