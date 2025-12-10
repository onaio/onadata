# -*- coding: utf-8 -*-
"""
Test api_export_tools module.
"""

import datetime
from collections import OrderedDict, defaultdict
from unittest.mock import Mock, patch

from django.http import Http404
from django.test.utils import override_settings

from celery.backends.rpc import BacklogLimitExceeded
from google.oauth2.credentials import Credentials
from kombu.exceptions import OperationalError
from rest_framework.request import Request

from onadata.apps.logger.models import XForm
from onadata.apps.main.models import TokenStorageModel
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export, ExportConnectionError
from onadata.libs.exceptions import ServiceUnavailable
from onadata.libs.utils.api_export_tools import (
    _get_google_credential,
    create_export_async,
    get_async_response,
    get_existing_file_format,
    get_metadata_format,
    process_async_export,
    response_for_format,
)
from onadata.libs.utils.async_status import SUCCESSFUL, status_msg


class TestApiExportTools(TestBase):
    """
    Test api_export_tools.
    """

    google_credential = {
        "refresh_token": "refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "scopes": ["https://www.googleapis.com/auth/drive.file"],
        "expiry": datetime.datetime(2016, 8, 18, 12, 43, 30, 316792),
    }

    def _create_old_export(self, xform, export_type, options, filename=None):
        options = OrderedDict(sorted(options.items()))
        Export(
            xform=xform,
            export_type=export_type,
            options=options,
            filename=filename,
            internal_status=Export.SUCCESSFUL,
        ).save()
        # pylint: disable=attribute-defined-outside-init
        self.export = Export.objects.filter(xform=xform, export_type=export_type)[0]

    def test_get_google_credentials(self):
        """
        Test create_async_export deletes credential when invalid
        """
        request = self.factory.get("/")
        request.user = self.user
        request.query_params = {}
        request.data = {}
        credential = self.google_credential
        t = TokenStorageModel(
            id=self.user, credential=Credentials(**credential, token=None)
        )
        t.save()
        self.assertFalse(t.credential.valid)
        response = _get_google_credential(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url[:71],
            "https://accounts.google.com/o/oauth2/auth?response_type=code&client_id=",
        )
        with self.assertRaises(TokenStorageModel.DoesNotExist):
            TokenStorageModel.objects.get(id=self.user)

    def test_get_google_credentials_valid(self):
        """
        Test create_async_export does not get rid of valid credential
        """

        request = self.factory.get("/")
        request.user = self.user
        request.query_params = {}
        request.data = {}
        self.google_credential["expiry"] = (
            datetime.datetime.utcnow() + datetime.timedelta(seconds=300)
        )
        credential = self.google_credential
        t = TokenStorageModel(
            id=self.user, credential=Credentials(**credential, token="token")
        )
        t.save()
        self.assertTrue(t.credential.valid)
        credential = _get_google_credential(request)

        self.assertEqual(credential.to_json(), t.credential.to_json())

    # pylint: disable=invalid-name
    def test_process_async_export_creates_new_export(self):
        """
        Test process_async_export creates a new export.
        """
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post("/")
        request.user = self.user
        export_type = "csv"
        options = defaultdict(dict)

        resp = process_async_export(request, self.xform, export_type, options=options)

        self.assertIn("job_uuid", resp)

    # pylint: disable=invalid-name
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_process_async_export_returns_existing_export(self):
        """
        Test process_async_export returns existing export.
        """
        self._publish_transportation_form_and_submit_instance()
        options = {
            "group_delimiter": "/",
            "remove_group_name": False,
            "split_select_multiples": True,
        }

        request = Request(self.factory.post("/"))
        request.user = self.user
        export_type = "csv"

        self._create_old_export(
            self.xform, export_type, options, filename="test_async_export"
        )

        resp = process_async_export(request, self.xform, export_type, options=options)

        self.assertEqual(resp["job_status"], status_msg[SUCCESSFUL])
        self.assertIn("export_url", resp)

    # pylint: disable=invalid-name
    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_get_async_response_export_does_not_exist(self, AsyncResult):
        """
        Test get_async_response export does not exist.
        """

        class MockAsyncResult(object):  # pylint: disable=R0903
            """Mock AsyncResult"""

            def __init__(self):
                self.state = "SUCCESS"
                self.result = 1

        AsyncResult.return_value = MockAsyncResult()
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post("/")
        request.user = self.user

        with self.assertRaises(Http404):
            get_async_response("job_uuid", request, self.xform)

    # pylint: disable=invalid-name
    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_get_async_response_export_backlog_limit(self, AsyncResult):
        """
        Test get_async_response export backlog limit exceeded.
        """

        class MockAsyncResult(object):  # pylint: disable=R0903
            """Mock AsyncResult"""

            def __init__(self):
                pass

            @property
            def state(self):
                """Raise BacklogLimitExceeded"""
                raise BacklogLimitExceeded()

        AsyncResult.return_value = MockAsyncResult()
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post("/")
        request.user = self.user

        result = get_async_response("job_uuid", request, self.xform)
        self.assertEqual(result, {"job_status": "PENDING"})

    def test_response_for_format(self):
        """
        Test response format type.
        """
        self._publish_xlsx_file()
        xform = XForm.objects.filter().last()
        self.assertIsNotNone(xform)
        self.assertIsInstance(response_for_format(xform).data, dict)
        self.assertIsInstance(response_for_format(xform, "json").data, dict)
        self.assertTrue(hasattr(response_for_format(xform, "xls").data, "file"))

        xform.xls.storage.delete(xform.xls.name)
        with self.assertRaises(Http404):
            response_for_format(xform, "xls")

    def test_get_metadata_format(self):
        """
        Test metadata export format/ext.
        """
        self._publish_xlsx_file()
        xform = XForm.objects.filter().last()
        data_value = "xform_geojson {} {}".format(xform.pk, xform.id_string)
        fmt = get_metadata_format(data_value)
        self.assertEqual("geojson", fmt)
        data_value = "dataview_geojson {} {}".format(xform.pk, xform.id_string)
        fmt = get_metadata_format(data_value)
        self.assertEqual("geojson", fmt)
        data_value = "xform {} {}".format(xform.pk, xform.id_string)
        fmt = get_metadata_format(data_value)
        self.assertEqual(fmt, "csv")

    def test_get_existing_file_format(self):
        """
        Test existing form download format/ext.
        """
        self._publish_xlsx_file()
        xform = XForm.objects.filter().last()
        fmt = get_existing_file_format(xform.xls, "xlsx")
        self.assertEqual("xlsx", fmt)
        # ensure it picks existing file extension regardless
        # of format passed in request params
        fmt = get_existing_file_format(xform.xls, "xls")
        self.assertEqual("xlsx", fmt)

    # pylint: disable=invalid-name
    @patch("onadata.libs.utils.api_export_tools.viewer_task.create_async_export")
    def test_process_async_export_connection_error(self, mock_task):
        """
        Test process_async_export creates a new export.
        """
        mock_task.side_effect = ExportConnectionError
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post("/")
        request.user = self.user
        export_type = "csv"
        options = defaultdict(dict)

        with self.assertRaises(ServiceUnavailable):
            process_async_export(request, self.xform, export_type, options=options)

    # pylint: disable=invalid-name
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    def test_get_async_response_connection_error(self, AsyncResult):
        """
        Test get_async_response connection error.
        """
        AsyncResult.side_effect = OperationalError
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post("/")
        request.user = self.user

        with self.assertRaises(ServiceUnavailable):
            get_async_response("job_uuid", request, self.xform)

    @patch("onadata.libs.utils.api_export_tools.AsyncResult")
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_get_async_response_when_result_changes_in_subsequent_calls(
        self, AsyncResult
    ):
        """
        Test get_async_response export does not exist.
        """

        class MockAsyncResult(object):  # pylint: disable=R0903
            """Mock AsyncResult"""

            res = [1, {"PENDING": "PENDING"}]

            def __init__(self):
                self.state = "PENDING"

            @property
            def result(self):
                """Return different states depending on when it's called"""
                return self.res.pop()

        AsyncResult.return_value = MockAsyncResult()
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post("/")
        request.user = self.user

        result = get_async_response("job_uuid", request, self.xform)
        self.assertEqual(result, {"job_status": "PENDING", "progress": "1"})

    # pylint: disable=invalid-name
    @patch("onadata.libs.utils.api_export_tools.send_message.delay")
    @patch("onadata.libs.utils.api_export_tools.viewer_task.create_async_export")
    @patch("onadata.libs.utils.api_export_tools.check_pending_export")
    def test_create_export_async_sends_message(
        self, mock_check_pending, mock_create_async_export, mock_send_message
    ):
        """
        Test that create_export_async sends a message when export is created.
        """

        self._publish_transportation_form_and_submit_instance()

        # Reset the mock to ignore any send_message calls from setup
        mock_send_message.reset_mock()

        # Mock no pending export
        mock_check_pending.return_value = None

        # Mock the export and async result
        mock_export = Export(id=123)
        mock_async_result = Mock()
        mock_async_result.task_id = "test-task-id"
        mock_create_async_export.return_value = (mock_export, mock_async_result)

        export_type = "csv"
        options = {}
        task_id = create_export_async(
            self.xform,
            export_type,
            query=None,
            force_xlsx=False,
            options=options,
            user=self.user,
        )

        self.assertEqual(task_id, "test-task-id")
        mock_send_message.assert_called_once_with(
            instance_id=123,
            target_id=self.xform.id,
            target_type="xform",
            user=self.user.id,
            message_verb="export_created",
            message_description="csv",
        )

    # pylint: disable=invalid-name
    @patch("onadata.libs.utils.api_export_tools.send_message.delay")
    @patch("onadata.libs.utils.api_export_tools.viewer_task.create_async_export")
    @patch("onadata.libs.utils.api_export_tools.check_pending_export")
    def test_create_export_async_no_message_when_export_fails(
        self, mock_check_pending, mock_create_async_export, mock_send_message
    ):
        """
        Test that create_export_async doesn't send a message when export creation returns None.
        """
        self._publish_transportation_form_and_submit_instance()

        # Reset the mock to ignore any send_message calls from setup
        mock_send_message.reset_mock()

        # Mock no pending export
        mock_check_pending.return_value = None

        # Mock the create_async_export to return None
        mock_create_async_export.return_value = None

        export_type = "csv"
        options = {}
        task_id = create_export_async(
            self.xform,
            export_type,
            query=None,
            force_xlsx=False,
            options=options,
            user=self.user,
        )

        self.assertIsNone(task_id)
        mock_send_message.assert_not_called()
