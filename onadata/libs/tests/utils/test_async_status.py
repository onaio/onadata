"""
tests for celery asyncronous task utilities
"""
from datetime import datetime
from unittest.mock import MagicMock

from celery import states
from onadata.apps.main.tests.test_base import TestBase
from onadata.celeryapp import app
from onadata.libs.utils import async_status
from onadata.apps.logger.models.xform import XForm


class TestAsyncStatus(TestBase):

    def test_celery_state_to_status(self):
        self.assertEqual(async_status.PENDING,
                         async_status.celery_state_to_status(states.PENDING))
        self.assertEqual(async_status.STARTED,
                         async_status.celery_state_to_status(states.STARTED))
        self.assertEqual(async_status.RETRY,
                         async_status.celery_state_to_status(states.RETRY))
        self.assertEqual(async_status.FAILED,
                         async_status.celery_state_to_status(states.FAILURE))
        self.assertEqual(async_status.SUCCESSFUL,
                         async_status.celery_state_to_status(states.SUCCESS))
        self.assertEqual(async_status.FAILED,
                         async_status.celery_state_to_status('123456'))

    def test_async_status(self):
        self.assertEqual(async_status.status_msg[async_status.PENDING],
                         async_status.async_status(async_status.PENDING)
                         .get('job_status'))
        self.assertEqual(async_status.status_msg[async_status.SUCCESSFUL],
                         async_status.async_status(async_status.SUCCESSFUL)
                         .get('job_status'))
        self.assertEqual(async_status.status_msg[async_status.FAILED],
                         async_status.async_status(async_status.FAILED)
                         .get('job_status'))
        self.assertTrue(async_status.
                        async_status(async_status.FAILED, 'has error')
                        .get('error'))
        self.assertFalse(async_status.
                         async_status(async_status.SUCCESSFUL).get('error'))

    def test_get_active_tasks(self):
        """test get_active_tasks"""
        xform = XForm()
        time_start = 1664372983.8631873
        self.assertEqual(
            async_status.get_active_tasks(
                ['onadata.libs.utils.csv_import.submit_csv_async'], xform
            ),
            [],
        )
        inspect = MagicMock()
        inspect.active = MagicMock(
            return_value={
                'celery-worker@onadata-id-1': [
                    {
                        'args': [None, xform.pk, "/home/ona/import.csv", True],
                        'id': '11',
                        'time_start': time_start,
                        'name': 'onadata.libs.utils.csv_import.submit_csv_async',
                    }
                ]
            }
        )
        app.control.inspect = MagicMock(return_value=inspect)

        self.assertEqual(async_status.get_active_tasks(
            ['onadata.libs.utils.csv_import.submit_csv_async'],
            xform),
            [{'job_uuid': '11',
              'time_start': datetime.fromtimestamp(time_start).strftime(
                  "%Y-%m-%dT%H:%M:%S"),
              "file": "/home/ona/import.csv", "overwrite": True}])
