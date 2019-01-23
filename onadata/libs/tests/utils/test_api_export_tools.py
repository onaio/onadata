# -*- coding=utf-8 -*-
"""
Test api_export_tools module.
"""
from collections import OrderedDict, defaultdict

import mock
from celery.backends.amqp import BacklogLimitExceeded
from django.http import Http404
from django.test.utils import override_settings
from kombu.exceptions import OperationalError
from rest_framework.request import Request

from onadata.apps.logger.models import XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export, ExportConnectionError
from onadata.libs.exceptions import ServiceUnavailable
from onadata.libs.utils.api_export_tools import (
    get_async_response, process_async_export, response_for_format)
from onadata.libs.utils.async_status import SUCCESSFUL, status_msg


class TestApiExportTools(TestBase):
    """
    Test api_export_tools.
    """

    def _create_old_export(self, xform, export_type, options, filename=None):
        options = OrderedDict(sorted(options.items()))
        Export(
            xform=xform,
            export_type=export_type,
            options=options,
            filename=filename,
            internal_status=Export.SUCCESSFUL).save()
        # pylint: disable=attribute-defined-outside-init
        self.export = Export.objects.filter(
            xform=xform, export_type=export_type)[0]

    # pylint: disable=invalid-name
    def test_process_async_export_creates_new_export(self):
        """
        Test process_async_export creates a new export.
        """
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post('/')
        request.user = self.user
        export_type = "csv"
        options = defaultdict(dict)

        resp = process_async_export(
            request, self.xform, export_type, options=options)

        self.assertIn('job_uuid', resp)

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
            "split_select_multiples": True
        }

        request = Request(self.factory.post('/'))
        request.user = self.user
        export_type = "csv"

        self._create_old_export(
            self.xform, export_type, options, filename="test_async_export")

        resp = process_async_export(
            request, self.xform, export_type, options=options)

        self.assertEquals(resp['job_status'], status_msg[SUCCESSFUL])
        self.assertIn("export_url", resp)

    # pylint: disable=invalid-name
    @mock.patch('onadata.libs.utils.api_export_tools.AsyncResult')
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_get_async_response_export_does_not_exist(self, AsyncResult):
        """
        Test get_async_response export does not exist.
        """

        class MockAsyncResult(object):  # pylint: disable=R0903
            """Mock AsyncResult"""

            def __init__(self):
                self.state = 'SUCCESS'
                self.result = 1

        AsyncResult.return_value = MockAsyncResult()
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post('/')
        request.user = self.user

        with self.assertRaises(Http404):
            get_async_response('job_uuid', request, self.xform)

    # pylint: disable=invalid-name
    @mock.patch('onadata.libs.utils.api_export_tools.AsyncResult')
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
        request = self.factory.post('/')
        request.user = self.user

        result = get_async_response('job_uuid', request, self.xform)
        self.assertEqual(result, {'job_status': 'PENDING'})

    def test_response_for_format(self):
        """
        Test response format type.
        """
        self._publish_xlsx_file()
        xform = XForm.objects.filter().last()
        self.assertIsNotNone(xform)
        self.assertIsInstance(response_for_format(xform).data, dict)
        self.assertIsInstance(response_for_format(xform, 'json').data, dict)
        self.assertTrue(
            hasattr(response_for_format(xform, 'xls').data, 'file'))

        xform.xls.storage.delete(xform.xls.name)
        with self.assertRaises(Http404):
            response_for_format(xform, 'xls')

    # pylint: disable=invalid-name
    @mock.patch(
        'onadata.libs.utils.api_export_tools.viewer_task.create_async_export')
    def test_process_async_export_connection_error(self, mock_task):
        """
        Test process_async_export creates a new export.
        """
        mock_task.side_effect = ExportConnectionError
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post('/')
        request.user = self.user
        export_type = "csv"
        options = defaultdict(dict)

        with self.assertRaises(ServiceUnavailable):
            process_async_export(
                request, self.xform, export_type, options=options)

    # pylint: disable=invalid-name
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @mock.patch('onadata.libs.utils.api_export_tools.AsyncResult')
    def test_get_async_response_connection_error(self, AsyncResult):
        """
        Test get_async_response connection error.
        """
        AsyncResult.side_effect = OperationalError
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post('/')
        request.user = self.user

        with self.assertRaises(ServiceUnavailable):
            get_async_response('job_uuid', request, self.xform)

    @mock.patch('onadata.libs.utils.api_export_tools.AsyncResult')
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_get_async_response_when_result_changes_in_subsequent_calls(
            self, AsyncResult):
        """
        Test get_async_response export does not exist.
        """

        class MockAsyncResult(object):  # pylint: disable=R0903
            """Mock AsyncResult"""
            res = [1, {'PENDING': 'PENDING'}]

            def __init__(self):
                self.state = "PENDING"

            @property
            def result(self):
                """Return different states depending on when it's called"""
                return self.res.pop()

        AsyncResult.return_value = MockAsyncResult()
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post('/')
        request.user = self.user

        result = get_async_response('job_uuid', request, self.xform)
        self.assertEqual(result, {'job_status': 'PENDING', 'progress': '1'})
