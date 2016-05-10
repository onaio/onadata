import os

from mock import patch, Mock
from ssl import SSLError

from django.utils import timezone
from django.conf import settings
from django.test.utils import override_settings

from oauth2client.contrib.django_orm import Storage
from oauth2client.client import AccessTokenCredentials

from onadata.apps.main.models import TokenStorageModel
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.restservice.models import RestService
from onadata.apps.restservice.viewsets.restservices_viewset import \
    RestServicesViewSet
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.utils.common_tags import GOOGLE_SHEET
from onadata.libs.utils.google_sheets import SheetsExportBuilder, SheetsClient


class TestRestServicesViewSet(TestAbstractViewSet):

    def setUp(self):
        super(TestRestServicesViewSet, self).setUp()
        self.view = RestServicesViewSet.as_view({
            'delete': 'destroy',
            'get': 'retrieve',
            'post': 'create',
            'put': 'update'
        })
        self._publish_xls_form_to_project()

    def test_create(self):
        count = RestService.objects.all().count()

        post_data = {
            "name": "generic_json",
            "service_url": "https://textit.io",
            "xform": self.xform.pk
        }
        request = self.factory.post('/', data=post_data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 201)
        self.assertEquals(count + 1, RestService.objects.all().count())

    def test_textit_service_missing_params(self):
        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
        }
        request = self.factory.post('/', data=post_data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 400)

    def _create_textit_service(self):
        count = RestService.objects.all().count()

        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda"
        }
        request = self.factory.post('/', data=post_data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 201)
        self.assertEquals(count + 1, RestService.objects.all().count())

        meta = MetaData.objects.filter(object_id=self.xform.id,
                                       data_type='textit')
        self.assertEquals(len(meta), 1)

        return response.data

    def test_create_textit_service(self):
        self._create_textit_service()

    def test_retrieve_textit_services(self):
        response_data = self._create_textit_service()

        _id = response_data.get('id')

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=_id)
        expected_dict = {
            'name': u'textit',
            'contacts': u'ksadaskjdajsda',
            'auth_token': u'sadsdfhsdf',
            'flow_uuid': u'sdfskhfskdjhfs',
            'service_url': u'https://textit.io',
            'id': _id,
            'xform': self.xform.pk
        }
        self.assertEqual(response.data, expected_dict)

    def test_delete_textit_service(self):
        rest = self._create_textit_service()
        count = RestService.objects.all().count()
        meta_count = MetaData.objects.filter(object_id=self.xform.id,
                                             data_type='textit').count()

        request = self.factory.delete('/', **self.extra)
        response = self.view(request, pk=rest['id'])

        self.assertEquals(response.status_code, 204)
        self.assertEquals(count - 1, RestService.objects.all().count())
        a_meta_count = MetaData.objects.filter(object_id=self.xform.id,
                                               data_type='textit').count()
        self.assertEqual(meta_count - 1, a_meta_count)

    def test_update(self):
        rest = RestService(name="testservice",
                           service_url="http://serviec.io",
                           xform=self.xform)
        rest.save()

        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda"
        }

        request = self.factory.put('/', data=post_data, **self.extra)
        response = self.view(request, pk=rest.pk)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data['name'], "textit")

    def test_delete(self):
        rest = RestService(name="testservice",
                           service_url="http://serviec.io",
                           xform=self.xform)
        rest.save()

        count = RestService.objects.all().count()

        request = self.factory.delete('/', **self.extra)
        response = self.view(request, pk=rest.pk)

        self.assertEquals(response.status_code, 204)
        self.assertEquals(count - 1, RestService.objects.all().count())

    def test_retrieve(self):
        rest = RestService(name="testservice",
                           service_url="http://serviec.io",
                           xform=self.xform)
        rest.save()

        request = self.factory.get('/', **self.extra)
        response = self.view(request, pk=rest.pk)

        data = {
            'id': rest.pk,
            'xform': self.xform.pk,
            'name': u'testservice',
            'service_url': u'http://serviec.io'
        }
        self.assertEquals(response.status_code, 200)

        self.assertEquals(response.data, data)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    @patch('httplib2.Http')
    def test_textit_flow(self, mock_http):
        rest = RestService(name="textit",
                           service_url="https://server.io",
                           xform=self.xform)
        rest.save()

        MetaData.textit(self.xform,
                        data_value='{}|{}|{}'.format("sadsdfhsdf",
                                                     "sdfskhfskdjhfs",
                                                     "ksadaskjdajsda"))

        self.assertFalse(mock_http.called)
        self._make_submissions()

        self.assertTrue(mock_http.called)
        self.assertEquals(mock_http.call_count, 4)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    @patch('httplib2.Http')
    def test_textit_flow_without_parsed_instances(self, mock_http):
        rest = RestService(name="textit",
                           service_url="https://server.io",
                           xform=self.xform)
        rest.save()

        MetaData.textit(self.xform,
                        data_value='{}|{}|{}'.format("sadsdfhsdf",
                                                     "sdfskhfskdjhfs",
                                                     "ksadaskjdajsda"))
        self.assertFalse(mock_http.called)
        self._make_submissions()

    def _create_google_sheet_service(self, data=None):
        storage = Storage(TokenStorageModel, 'id', self.user, 'credential')
        google_creds = AccessTokenCredentials("fake_token", user_agent="onaio")
        google_creds.set_store(storage)
        storage.put(google_creds)

        count = RestService.objects.all().count()

        post_data = {
            "name": GOOGLE_SHEET,
            "xform": self.xform.pk,
            "google_sheet_title": "Data-sync",
            "send_existing_data": False,
            "sync_updates": False
        }

        if data:
            post_data.update(data)

        request = self.factory.post('/', data=post_data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 201)
        self.assertEquals(count + 1, RestService.objects.all().count())

        google_sheet_details = MetaData.get_google_sheet_details(self.xform)
        self.assertIsNotNone(google_sheet_details)

        return response.data

    @patch.object(SheetsExportBuilder, 'live_update')
    @patch.object(SheetsClient, 'get_google_sheet_id')
    def test_create_google_sheets_service(self, mock_sheet_client,
                                          mock_sheet_builder):
        mock_sheet_client.return_value = "very_mocked_id"
        self._create_google_sheet_service()

        self.assertTrue(mock_sheet_client.called)
        self.assertFalse(mock_sheet_builder.called)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    @patch.object(SheetsExportBuilder, 'live_update')
    @patch.object(SheetsClient, 'get_google_sheet_id')
    def test_create_google_sheets_service_w_initial_upload(self,
                                                           mock_sheet_client,
                                                           mock_sheet_builder):
        mock_sheet_client.return_value = "very_mocked_id"
        self._make_submissions()
        self._create_google_sheet_service({"send_existing_data": True})

        self.assertTrue(mock_sheet_client.called)
        self.assertTrue(mock_sheet_builder.called)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    @patch.object(SheetsExportBuilder, 'live_update')
    @patch.object(SheetsClient, 'get_google_sheet_id')
    def test_create_google_sheets_service_submission(self, mock_sheet_client,
                                                     mock_sheet_builder):
        mock_sheet_client.return_value = "very_mocked_id"
        self._create_google_sheet_service({"send_existing_data": True})

        self.assertTrue(mock_sheet_client.called)

        # should not be called because we dont have submission
        self.assertFalse(mock_sheet_builder.called)

        self._make_submissions()

        # called four times
        self.assertEqual(4, mock_sheet_builder.call_count)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    @patch.object(SheetsExportBuilder, 'live_update')
    @patch.object(SheetsClient, 'get_google_sheet_id')
    def test_edit_submission_google_sheets_service(self, mock_sheet_client,
                                                   mock_sheet_builder):
        xls_file_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "logger",
            "fixtures", "tutorial", "tutorial.xls"
        )

        self._publish_xls_form_to_project(xlsform_path=xls_file_path)

        mock_sheet_client.return_value = "very_mocked_id"
        self._create_google_sheet_service()

        self.assertTrue(mock_sheet_client.called)

        submission_count = self.xform.instances.count()

        xml_submission_file_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "logger", "fixtures", "tutorial",
            "instances", "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )

        self._make_submission(xml_submission_file_path)

        self.assertEqual(submission_count + 1, self.xform.instances.count())

        self.assertEqual(1, mock_sheet_builder.call_count)
        instance = self.xform.instances.last()
        mock_sheet_builder.assert_called_with(None, [instance.json],
                                              self.xform,
                                              spreadsheet_id=u'very_mocked_id')
        mock_sheet_builder.reset_mock()

        xml_edit_submission_file_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "logger", "fixtures", "tutorial",
            "instances", "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml"
        )

        self._make_submission(xml_edit_submission_file_path)
        self.assertEqual(submission_count + 1, self.xform.instances.count())
        self.assertEqual(1, mock_sheet_builder.call_count)
        instance = self.xform.instances.last()

        mock_sheet_builder.assert_called_with(None, [instance.json],
                                              self.xform,
                                              spreadsheet_id=u'very_mocked_id',
                                              update=True)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    @patch.object(SheetsExportBuilder, 'live_update')
    @patch.object(SheetsClient, 'get_google_sheet_id')
    def test_delete_submission_google_sheets_service(self, mock_sheet_client,
                                                     mock_sheet_builder):
        xls_file_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "logger",
            "fixtures", "tutorial", "tutorial.xls"
        )

        self._publish_xls_form_to_project(xlsform_path=xls_file_path)

        mock_sheet_client.return_value = "very_mocked_id"
        self._create_google_sheet_service()

        self.assertTrue(mock_sheet_client.called)

        xml_submission_file_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "logger", "fixtures",
            "tutorial",
            "instances", "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )

        self._make_submission(xml_submission_file_path)

        self.assertEqual(1, mock_sheet_builder.call_count)
        instance = self.xform.instances.last()
        mock_sheet_builder.assert_called_with(None, [instance.json],
                                              self.xform,
                                              spreadsheet_id=u'very_mocked_id')
        mock_sheet_builder.reset_mock()

        instance = self.xform.instances.last()

        # delete submission
        instance.set_deleted(timezone.now())
        self.assertEqual(1, mock_sheet_builder.call_count)

        mock_sheet_builder.assert_called_with(None, instance.pk, self.xform,
                                              spreadsheet_id=u'very_mocked_id',
                                              delete=True)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    @patch.object(SheetsExportBuilder, 'live_update',
                  side_effect=[SSLError(), SSLError(), Mock()])
    @patch.object(SheetsClient, 'get_google_sheet_id')
    def test_google_sheets_service_retries(self, mock_sheet_client,
                                           mock_sheet_builder):
        xls_file_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "logger",
            "fixtures", "tutorial", "tutorial.xls"
        )

        self._publish_xls_form_to_project(xlsform_path=xls_file_path)

        mock_sheet_client.return_value = "very_mocked_id"
        self._create_google_sheet_service()

        self.assertTrue(mock_sheet_client.called)

        xml_submission_file_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "logger", "fixtures",
            "tutorial",
            "instances", "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )

        self._make_submission(xml_submission_file_path)

        self.assertEqual(3, mock_sheet_builder.call_count)
        instance = self.xform.instances.last()
        mock_sheet_builder.assert_called_with(None, [instance.json],
                                              self.xform,
                                              spreadsheet_id=u'very_mocked_id')

    @override_settings(CELERY_ALWAYS_EAGER=True)
    @patch.object(SheetsExportBuilder, 'live_update',
                  side_effect=[SSLError(), SSLError(), SSLError()])
    @patch.object(SheetsClient, 'get_google_sheet_id')
    def test_google_sheets_service_retries_all_fail(self, mock_sheet_client,
                                                    mock_sheet_builder):
        xls_file_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "logger",
            "fixtures", "tutorial", "tutorial.xls"
        )

        self._publish_xls_form_to_project(xlsform_path=xls_file_path)

        mock_sheet_client.return_value = "very_mocked_id"
        self._create_google_sheet_service()

        self.assertTrue(mock_sheet_client.called)

        xml_submission_file_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "logger", "fixtures",
            "tutorial",
            "instances", "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )

        self._make_submission(xml_submission_file_path)

        self.assertEqual(4, mock_sheet_builder.call_count)
