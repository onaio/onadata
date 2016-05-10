from mock import patch

from rest_framework.test import APIRequestFactory
from rest_framework.serializers import ValidationError

from django.contrib.auth.models import AnonymousUser

from oauth2client.contrib.django_orm import Storage
from oauth2client.client import AccessTokenCredentials

from onadata.apps.main.models import TokenStorageModel
from onadata.apps.restservice.models import RestService
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.libs.serializers.google_serializer import GoogleSheetsSerializer
from onadata.libs.utils.google_sheets import SheetsClient


class TestGoogleSheetSerializer(TestAbstractViewSet):

    def setUp(self):
        self.factory = APIRequestFactory()
        self._login_user_and_profile()

    @patch.object(SheetsClient, 'get_google_sheet_id')
    def test_create_google_sheet_service(self, mock_sheet_client):
        mock_sheet_client.return_value = "very_mocked_id"
        # create a project with a form
        self._publish_xls_form_to_project()
        storage = Storage(TokenStorageModel, 'id', self.user, 'credential')
        google_creds = AccessTokenCredentials("fake_token", user_agent="onaio")
        google_creds.set_store(storage)
        storage.put(google_creds)

        request = self.factory.post('/', **self.extra)
        request.user = self.user

        pre_count = RestService.objects.filter(xform=self.xform).count()

        data = {
            "xform": self.xform.pk,
            "name": "google_sheets",
            "google_sheet_title": "Data-sync",
            "send_existing_data": False,
            "sync_updates": False
        }

        serializer = GoogleSheetsSerializer(data=data,
                                            context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        count = RestService.objects.filter(xform=self.xform).count()

        self.assertEqual(pre_count + 1, count)

        gsheet_details = MetaData.get_google_sheet_details(self.xform)
        self.assertEqual(gsheet_details.get('USER_ID'),
                         '{}'.format(self.user.pk))
        self.assertEqual(gsheet_details.get('GOOGLE_SHEET_ID'),
                         "very_mocked_id")
        self.assertEqual(
            gsheet_details.get('UPDATE_OR_DELETE_GOOGLE_SHEET_DATA'), 'False')

    def test_create_google_sheet_webhook_with_no_google_credential(self):
        # create a project with a form
        self._publish_xls_form_to_project()

        request = self.factory.post('/', **self.extra)
        request.user = self.user

        pre_count = RestService.objects.filter(xform=self.xform).count()

        data = {
            "xform": self.xform.pk,
            "name": "google_sheets",
            "google_sheet_title": "Data-sync",
            "send_existing_data": False,
            "sync_updates": False
        }

        serializer = GoogleSheetsSerializer(data=data,
                                            context={'request': request})
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)
            serializer.save()

        count = RestService.objects.filter(xform=self.xform).count()

        self.assertEqual(pre_count, count)
        gsheet_details = MetaData.get_google_sheet_details(self.xform)
        self.assertIsNone(gsheet_details)

    def test_create_google_sheet_webhook_without_auth(self):
        # create a project with a form
        self._publish_xls_form_to_project()

        request = self.factory.post('/')
        request.user = AnonymousUser()

        pre_count = RestService.objects.filter(xform=self.xform).count()

        data = {
            "xform": self.xform.pk,
            "name": "google_sheets",
            "google_sheet_title": "Data-sync",
            "send_existing_data": False,
            "sync_updates": False
        }

        serializer = GoogleSheetsSerializer(data=data,
                                            context={'request': request})
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)
            serializer.save()

        count = RestService.objects.filter(xform=self.xform).count()

        self.assertEqual(pre_count, count)
        gsheet_details = MetaData.get_google_sheet_details(self.xform)
        self.assertIsNone(gsheet_details)

    @patch.object(SheetsClient, 'get_google_sheet_id')
    def test_update_google_sheet_service(self, mock_sheet_client):
        mock_sheet_client.return_value = "very_mocked_id"
        # create a project with a form
        self._publish_xls_form_to_project()
        storage = Storage(TokenStorageModel, 'id', self.user, 'credential')
        google_creds = AccessTokenCredentials("fake_token", user_agent="onaio")
        google_creds.set_store(storage)
        storage.put(google_creds)

        request = self.factory.post('/', **self.extra)
        request.user = self.user

        pre_count = RestService.objects.filter(xform=self.xform).count()

        data = {
            "xform": self.xform.pk,
            "name": "google_sheets",
            "google_sheet_title": "Data-sync",
            "send_existing_data": False,
            "sync_updates": False
        }

        serializer = GoogleSheetsSerializer(data=data,
                                            context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        count = RestService.objects.filter(xform=self.xform).count()

        self.assertEqual(pre_count + 1, count)

        data = {
            "xform": self.xform.pk,
            "name": "google_sheets",
            "google_sheet_title": "Data-sync2",
            "send_existing_data": True,
            "sync_updates": True
        }
        mock_sheet_client.reset()
        mock_sheet_client.return_value = "very_mocked_id_2"

        rest_service = RestService.objects.get(xform=self.xform)

        serializer = GoogleSheetsSerializer(rest_service,
                                            data=data,
                                            context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        gsheet_details = MetaData.get_google_sheet_details(self.xform)
        self.assertEqual(gsheet_details.get('USER_ID'),
                         '{}'.format(self.user.pk))
        self.assertEqual(gsheet_details.get('GOOGLE_SHEET_ID'),
                         "very_mocked_id")
        self.assertEqual(gsheet_details.get('GOOGLE_SHEET_TITLE'),
                         "Data-sync2")
        self.assertEqual(
            gsheet_details.get('UPDATE_OR_DELETE_GOOGLE_SHEET_DATA'), 'True')
