"""
API tasks test
"""
from datetime import timedelta

from celery import current_app
from django.conf import settings
from django.test import override_settings

from onadata.apps.api.tasks import delete_inactive_submissions
from onadata.apps.main.tests.test_base import TestBase


class TestAPITasks(TestBase):
    """
    Test api tasks
    """

    def setUp(self):
        super().setUp()
        settings.CELERY_TASK_ALWAYS_EAGER = True
        current_app.conf.CELERY_TASK_ALWAYS_EAGER = True

    # pylint: disable=invalid-name
    @override_settings(INACTIVE_SUBMISSIONS_LIFESPAN=20)
    def test_delete_inactive_submissions_async(self): # noqa
        """Test delete_inactive_submissions() task"""
        self._publish_transportation_form()
        self._make_submissions()
        self.xform.refresh_from_db()
        # check submissions count
        self.assertEqual(self.xform.instances.count(), 4)
        # soft delete one of the instances
        instance = self.xform.instances.last()
        deleted_at = instance.date_created - timedelta(days=60)
        instance.set_deleted(deleted_at, self.user)
        # test that theres one soft deleted submission
        self.assertEqual(self.xform.instances.filter(deleted_at__isnull=False).count(), 1)
        delete_inactive_submissions()
        # test that the soft deleted submission is deleted
        # since deleted_at is greater than specified lifespan
        self.assertEqual(self.xform.instances.filter(deleted_at__isnull=False).count(), 0)
