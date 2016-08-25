import os

from django.conf import settings
from mock import patch

from oauth2client.client import OAuth2WebServerFlow, OAuth2Credentials,\
    FlowExchangeError

from onadata.apps.main.models import TokenStorageModel
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
        pk = 3
        for f in self.formats:
            request = self.factory.get('/export')
            response = self.view(request, pk=pk)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch.object(OAuth2WebServerFlow, 'step2_exchange')
    def test_google_auth(self, mock_oauth2):
        mock_oauth2.return_value = OAuth2Credentials("access_token",
                                                     "client_id",
                                                     "client_secret",
                                                     "refresh_token",
                                                     "token_expiry",
                                                     "token_uri", "user_agent")
        view = ExportViewSet.as_view({
            'get': 'google_auth'
        })
        creds_count = TokenStorageModel.objects.filter(id=self.user.id).count()

        data = {'code': 'codeexample'}
        request = self.factory.get('/', data=data)
        force_authenticate(request, user=self.user)
        response = view(request)

        self.assertEqual(response.status_code, 201)

        current_creds = TokenStorageModel.objects.filter(id=self.user.id) \
            .count()
        self.assertEqual(creds_count + 1, current_creds)

    def test_google_auth_authenticated(self):
        view = ExportViewSet.as_view({
            'get': 'google_auth'
        })
        creds_count = TokenStorageModel.objects.filter(id=self.user.id).count()

        data = {'code': 'codeexample'}
        # no authentication
        request = self.factory.get('/', data=data)
        response = view(request)

        self.assertEqual(response.status_code, 401)

        current_creds = TokenStorageModel.objects.filter(id=self.user.id) \
            .count()

        # creds not created
        self.assertEqual(creds_count, current_creds)

    @patch.object(OAuth2WebServerFlow, 'step2_exchange')
    def test_google_auth_flow2_exchange_error(self, mock_oauth2):
        mock_oauth2.side_effect = FlowExchangeError('invalid grant')
        view = ExportViewSet.as_view({
            'get': 'google_auth'
        })
        creds_count = TokenStorageModel.objects.filter(id=self.user.id).count()

        data = {'code': 'codeexample'}
        request = self.factory.get('/', data=data)
        force_authenticate(request, user=self.user)
        response = view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {
                u"details": u"invalid grant",
            })

        current_creds = TokenStorageModel.objects.filter(id=self.user.id) \
            .count()

        # creds not created
        self.assertEqual(creds_count, current_creds)
