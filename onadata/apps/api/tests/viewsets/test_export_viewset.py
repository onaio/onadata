# -*- coding: utf-8 -*-
"""
test_export_viewset module
"""

import os
from tempfile import NamedTemporaryFile

from django.conf import settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from onadata.apps.api.viewsets.export_viewset import ExportViewSet
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.export_tools import generate_export


class TestExportViewSet(TestBase):
    """
    Test ExportViewSet functionality.
    """

    def setUp(self):
        super(TestExportViewSet, self).setUp()
        self.factory = APIRequestFactory()
        self.formats = ['csv', 'csvzip', 'kml', 'osm', 'savzip', 'xls',
                        'xlsx', 'zip']
        self.view = ExportViewSet.as_view({'get': 'retrieve'})

    def test_export_response(self):
        """
        Test ExportViewSet retrieve has the correct headers in response.
        """
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

    def test_export_formats_present(self):
        """
        Test export formats are in ExportViewSet.renderer_classes.
        """
        renderer_formats = [rc.format for rc in self.view.cls.renderer_classes]

        for ext in self.formats:
            self.assertIn(ext, renderer_formats)

    def test_export_non_existent_file(self):
        """
        Test non existent primary key results in HTTP_404_NOT_FOUND.
        """
        self._create_user_and_login()
        non_existent_pk = 1525266252676
        for ext in self.formats:
            request = self.factory.get('/export')
            force_authenticate(request, user=self.user)
            response = self.view(request, pk=non_existent_pk, format=ext)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_list(self):
        """
        Test ExportViewSet list endpoint.
        """
        self._create_user_and_login()
        view = ExportViewSet.as_view({'get': 'list'})
        request = self.factory.get('/export')
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertFalse(bool(response.data))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_list_public(self):
        """
        Test ExportViewSet list endpoint for public forms.
        """
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
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertTrue(bool(response.data))
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_public_project(self):
        """
        Test export of a public form for anonymous users.
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        self.xform.shared_data = True
        self.xform.save()
        export = generate_export(Export.CSV_EXPORT,
                                 self.xform,
                                 None,
                                 {"extension": "csv"})
        request = self.factory.get('/export')
        response = self.view(request, pk=export.pk)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    # pylint: disable=C0103
    def test_export_public_authenticated(self):
        """
        Test export of a public form for authenticated users.
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        self.xform.shared_data = True
        self.xform.save()
        export = generate_export(Export.CSV_EXPORT,
                                 self.xform,
                                 None,
                                 {"extension": "csv"})
        request = self.factory.get('/export')
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=export.pk)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_export_non_public_export(self):
        """
        Test export of a private form for anonymous users results in
        HTTP_404_NOT_FOUND response.
        """
        self._create_user_and_login()
        self._publish_transportation_form()
        self.xform.shared_data = False
        self.xform.save()
        export = generate_export(Export.CSV_EXPORT,
                                 self.xform,
                                 None,
                                 {"extension": "csv"})
        request = self.factory.get('/export')
        response = self.view(request, pk=export.pk)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_export_list_on_user(self):
        """
        Test ExportViewSet list endpoint with xform filter.
        """
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
        """
        Test ExportViewSet list endpoint with a different user.
        """
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

    def test_export_delete(self):
        """
        Test deleting an export on ExportViewSet.
        """
        markdown_xlsform = """
        | survey |
        |        | type              | name  | label |
        |        | select one fruits | fruit | Fruit |

        | choices |
        |         | list name | name   | label  |
        |         | fruits    | orange | Orange |
        |         | fruits    | mango  | Mango  |
        """
        self._create_user_and_login()
        xform = self._publish_markdown(markdown_xlsform, self.user)
        bob = self.user
        export = Export.objects.create(xform=xform)
        export.save()
        view = ExportViewSet.as_view({'delete': 'destroy'})

        # mary has no access hence cannot delete
        self._create_user_and_login(username='mary', password='password1')
        request = self.factory.delete('/export')
        force_authenticate(request, user=self.user)
        response = view(request, pk=export.pk)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

        # bob has access hence can delete
        request = self.factory.delete('/export')
        force_authenticate(request, user=bob)
        response = view(request, pk=export.pk)
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
