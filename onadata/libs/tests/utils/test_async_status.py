from onadata.apps.main.tests.test_base import TestBase
from celery import states
from onadata.libs.utils import async_status


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
