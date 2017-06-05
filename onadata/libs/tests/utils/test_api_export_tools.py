from collections import OrderedDict, defaultdict

import mock
from celery import current_app
from celery.backends.amqp import BacklogLimitExceeded
from django.conf import settings
from django.http import Http404
from rest_framework.request import Request

from onadata.apps.logger.models import XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.api_export_tools import (get_async_response,
                                                 process_async_export,
                                                 response_for_format)
from onadata.libs.utils.async_status import SUCCESSFUL, status_msg


class TestApiExportTools(TestBase):
    def _create_old_export(self, xform, export_type, options, filename=None):
        options = OrderedDict(sorted(options.items()))
        Export(
            xform=xform,
            export_type=export_type,
            options=options,
            filename=filename,
            internal_status=Export.SUCCESSFUL).save()
        self.export = Export.objects.filter(
            xform=xform, export_type=export_type)[0]

    def test_process_async_export_creates_new_export(self):
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post('/')
        request.user = self.user
        export_type = "csv"
        options = defaultdict(dict)

        resp = process_async_export(
            request, self.xform, export_type, options=options)

        self.assertIn('job_uuid', resp)

    def test_process_async_export_returns_existing_export(self):
        settings.CELERY_ALWAYS_EAGER = True
        current_app.conf.CELERY_ALWAYS_EAGER = True

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

    @mock.patch('onadata.libs.utils.api_export_tools.AsyncResult')
    def test_get_async_response_export_does_not_exist(self, AsyncResult):
        class MockAsyncResult(object):
            def __init__(self):
                self.state = 'SUCCESS'
                self.result = 1

        AsyncResult.return_value = MockAsyncResult()
        settings.CELERY_ALWAYS_EAGER = True
        current_app.conf.CELERY_ALWAYS_EAGER = True
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post('/')
        request.user = self.user

        with self.assertRaises(Http404):
            get_async_response('job_uuid', request, self.xform)

    @mock.patch('onadata.libs.utils.api_export_tools.AsyncResult')
    def test_get_async_response_export_blacklog_limit(self, AsyncResult):
        class MockAsyncResult(object):
            def __init__(self):
                pass

            @property
            def state(self):
                raise BacklogLimitExceeded()

        AsyncResult.return_value = MockAsyncResult()
        settings.CELERY_ALWAYS_EAGER = True
        current_app.conf.CELERY_ALWAYS_EAGER = True
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post('/')
        request.user = self.user

        result = get_async_response('job_uuid', request, self.xform)
        self.assertEqual(result, {'job_status': 'PENDING'})

    def test_response_for_format(self):
        self._publish_xlsx_file()
        xform = XForm.objects.filter().last()
        self.assertIsNotNone(xform)
        self.assertIsInstance(response_for_format(xform).data, dict)
        self.assertIsInstance(response_for_format(xform, 'json').data, dict)
        self.assertTrue(hasattr(response_for_format(xform, 'xls').data,
                                'file'))

        xform.xls.storage.delete(xform.xls.name)
        with self.assertRaises(Http404):
            response_for_format(xform, 'xls')
