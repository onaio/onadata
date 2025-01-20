"""
API tasks test
"""
import os
from datetime import timedelta

from celery import current_app
from django.conf import settings
from django.core.files.storage import storages
from django.test import override_settings
from django.utils import timezone

from onadata.apps.api.tasks import delete_inactive_submissions
from onadata.apps.logger.models import Attachment
from onadata.apps.logger.models.instance import InstanceHistory
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
    def test_delete_inactive_submissions_async(self):  # noqa
        """Test delete_inactive_submissions() task"""
        self._publish_transportation_form()
        self._make_submissions()
        self.xform.refresh_from_db()
        # check submissions count
        self.assertEqual(self.xform.instances.count(), 4)
        # soft delete one of the instances
        instance = self.xform.instances.last()
        # set submission date_created to be 90 days from now
        instance.date_created = timezone.now() - timedelta(days=90)
        instance.save()
        # set deleted_at to be 60 days from now
        # meaning the submission is soft deleted 30 days after being created
        deleted_at = timezone.now() - timedelta(days=60)
        instance.set_deleted(deleted_at, self.user)
        # test that theres one soft deleted submission
        self.assertEqual(
            self.xform.instances.filter(deleted_at__isnull=False).count(), 1
        )
        delete_inactive_submissions()
        # test that the soft deleted submission is deleted
        # since deleted_at is greater than specified lifespan
        self.assertEqual(
            self.xform.instances.filter(deleted_at__isnull=False).count(), 0
        )

    # pylint: disable=invalid-name
    @override_settings(INACTIVE_SUBMISSIONS_LIFESPAN=20)
    def test_delete_inactive_submissions_with_attachments(self):  # noqa
        """Test delete_inactive_submissions() task"""
        self._publish_transportation_form()
        self._submit_transport_instance_w_attachment()
        self._submit_transport_instance_w_uuid("transport_2011-07-25_19-05-36")
        self.xform.refresh_from_db()
        # check submissions count
        self.assertEqual(self.xform.instances.count(), 2)
        # check attachments count
        self.assertEqual(Attachment.objects.all().count(), 1)
        # check if attachment file exists in file system
        default_storage = storages["default"]
        self.assertTrue(
            default_storage.exists(self.attachment.media_file.name)
        )
        instance = self.xform.instances.first()
        # create instance history
        s = self.surveys[0]
        xml_edit_submission_file_path = os.path.join(
            self.this_directory,
            "fixtures",
            "transportation",
            "instances",
            s,
            s + "_edited.xml",
        )
        # edit submission
        self._make_submission(xml_edit_submission_file_path)
        history_count = InstanceHistory.objects.filter(
            xform_instance__id=instance.pk
        ).count()
        self.assertEqual(history_count, 1)
        # set submission date_created to be 90 days from now
        instance.date_created = timezone.now() - timedelta(days=90)
        instance.save()
        # soft delete submission
        # set deleted_at to be 60 days from now
        # meaning the submission is soft deleted 30 days after being created
        deleted_at = timezone.now() - timedelta(days=60)
        instance.set_deleted(deleted_at, self.user)
        # test that theres one soft deleted submission
        self.assertEqual(
            self.xform.instances.filter(deleted_at__isnull=False).count(), 1
        )
        delete_inactive_submissions()
        # test that the soft deleted submission is deleted
        # since deleted_at is greater than specified lifespan
        self.assertEqual(
            self.xform.instances.filter(deleted_at__isnull=False).count(), 0
        )
        # test that the deletion cascades to InstanceHistory & attachments
        self.assertEqual(Attachment.objects.all().count(), 0)
        self.assertEqual(InstanceHistory.objects.all().count(), 0)
        # check that attachment doesn't exist in storage
        self.assertFalse(
            default_storage.exists(self.attachment.media_file.name)
        )
