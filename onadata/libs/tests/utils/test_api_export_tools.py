from celery import current_app
from collections import defaultdict

from django.conf import settings

from mock import patch
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer import tasks as viewer_task
from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.api_export_tools import (
    process_async_export)


class TestApiExportTools(TestBase):

    def _create_old_export(self, xform, export_type):
        Export(xform=xform,
               export_type=export_type,
               internal_status=Export.SUCCESSFUL).save()
        self.export = Export.objects.filter(
            xform=xform, export_type=export_type)[0]

    def test_process_async_export_creates_new_export(self):
        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post('/')
        export_type = "csv"
        options = defaultdict(dict)

        resp = process_async_export(
            request, self.xform, export_type, options=options)

        self.assertIn('job_uuid', resp)

    def test_process_async_export_returns_existing_export(self):
        settings.CELERY_ALWAYS_EAGER = True
        current_app.conf.CELERY_ALWAYS_EAGER = True

        self._publish_transportation_form_and_submit_instance()
        request = self.factory.post('/')
        export_type = "csv"
        options = {"group_delimiter": "/",
                   "remove_group_name": False,
                   "split_select_multiples": True}

        self._create_old_export(self.xform, export_type)

        with patch(
            'onadata.libs.utils.api_export_tools._create_export_async')\
                as mock_create_export:
            process_async_export(
                request, self.xform, export_type, options=options)

            export, async_result = viewer_task.create_async_export(
                self.xform, export_type, None, None, options=options)

            self.assertTrue(mock_create_export.called)

            self.assertEquals(self.export.id, export.id)
