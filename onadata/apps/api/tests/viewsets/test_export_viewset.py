import os

from django.conf import settings
from onadata.apps.api.viewsets.export_viewset import ExportViewSet
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export

from rest_framework.test import APIRequestFactory, force_authenticate

from tempfile import NamedTemporaryFile


class TestExportViewSet(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self.factory = APIRequestFactory()
        self.view = ExportViewSet.as_view({'get': 'retrieve'})

    def test_generates_expected_response(self):
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
        formats = ['csv', 'osm', 'xls', 'xlsx', 'csvzip', 'savzip']
        renderer_formats = [rc.format for rc in self.view.cls.renderer_classes]

        for f in formats:
            self.assertIn(f, renderer_formats)
