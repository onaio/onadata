import os

from django.test import RequestFactory

from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.main.tests.test_base import TestBase


class TestExportViewSet(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    def _filename_from_disposition(self, content_disposition):
        filename_pos = content_disposition.index('filename=')
        self.assertTrue(filename_pos != -1)
        return content_disposition[filename_pos + len('filename='):]

    def test_form_data_export(self):
        self._make_submissions()
        view = XFormViewSet.as_view({
            'get': 'retrieve'
        })
        formid = self.xform.pk
        # csv
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid, format='csv')
        self.assertEqual(response.status_code, 200)
        headers = dict(response.items())
        content_disposition = headers['Content-Disposition']
        filename = self._filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(headers['Content-Type'], 'application/csv')
        self.assertEqual(ext, '.csv')

        # xls
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid, format='xls')
        self.assertEqual(response.status_code, 200)
        headers = dict(response.items())
        content_disposition = headers['Content-Disposition']
        filename = self._filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(headers['Content-Type'],
                         'application/vnd.openxmlformats')
        self.assertEqual(ext, '.xlsx')

    def test_data_export(self):
        self._make_submissions()
        view = DataViewSet.as_view({
            'get': 'list'
        })
        formid = self.xform.pk
        # csv
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid, format='csv')
        self.assertEqual(response.status_code, 200)
        headers = dict(response.items())
        content_disposition = headers['Content-Disposition']
        filename = self._filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(headers['Content-Type'], 'application/csv')
        self.assertEqual(ext, '.csv')

        # xls
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid, format='xls')
        self.assertEqual(response.status_code, 200)
        headers = dict(response.items())
        content_disposition = headers['Content-Disposition']
        filename = self._filename_from_disposition(content_disposition)
        basename, ext = os.path.splitext(filename)
        self.assertEqual(headers['Content-Type'],
                         'application/vnd.openxmlformats')
        self.assertEqual(ext, '.xlsx')
