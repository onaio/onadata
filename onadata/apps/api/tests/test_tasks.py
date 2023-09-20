"""Tests for module onadata.apps.api.tasks"""
import logging
import sys

from unittest.mock import patch

from django.core.cache import cache

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.api.tasks import (
    send_project_invitation_email_async,
    regenerate_form_instance_json,
)
from onadata.apps.logger.models import ProjectInvitation, Instance
from onadata.libs.utils.user_auth import get_user_default_project
from onadata.libs.utils.email import ProjectInvitationEmail


class SendProjectInivtationEmailAsyncTestCase(TestBase):
    """Tests for send_project_invitation_email_async"""

    def setUp(self) -> None:
        super().setUp()

        project = get_user_default_project(self.user)
        self.invitation = ProjectInvitation.objects.create(
            project=project,
            email="janedoe@example.com",
            role="manager",
        )

    @patch.object(ProjectInvitationEmail, "send")
    def test_sends_email(self, mock_send):
        """Test email is sent"""
        url = "https://example.com/register"
        send_project_invitation_email_async(self.invitation.id, url)
        mock_send.assert_called_once()


class RegenerateFormInstanceJsonTestCase(TestBase):
    """Tests for regenerate_form_instance_json"""

    def test_regenerates_instances_json(self):
        """Regenerates instances json"""

        def mock_get_full_dict(self):  # pylint: disable=unused-argument
            return {}

        with patch.object(Instance, "get_full_dict", mock_get_full_dict):
            self._publish_transportation_form_and_submit_instance()

        cache_key = f"xfm-regenerate_instance_json_task-{self.xform.pk}"
        cache.set(cache_key, "foo")
        instance = self.xform.instances.first()
        self.assertFalse(instance.json)
        self.assertFalse(self.xform.is_instance_json_regenerated)
        regenerate_form_instance_json(self.xform.pk)
        instance.refresh_from_db()
        self.assertTrue(instance.json)
        self.xform.refresh_from_db()
        self.assertTrue(self.xform.is_instance_json_regenerated)
        # task_id stored in cache should be deleted
        self.assertIsNone(cache.get(cache_key))

    def test_json_overriden(self):
        """Existing json is overriden"""

        def mock_get_full_dict(self):  # pylint: disable=unused-argument
            return {"foo": "bar"}

        with patch.object(Instance, "get_full_dict", mock_get_full_dict):
            self._publish_transportation_form_and_submit_instance()

        instance = self.xform.instances.first()
        self.assertEqual(instance.json.get("foo"), "bar")
        regenerate_form_instance_json(self.xform.pk)
        instance.refresh_from_db()
        self.assertFalse("foo" in instance.json)

    def test_form_id_invalid(self):
        """An invalid xform_id is handled"""
        with self.assertLogs() as logs:
            regenerate_form_instance_json(sys.maxsize)

        self.assertEqual(len(logs.records), 1)
        self.assertEqual(
            logs.records[0].getMessage(), "XForm matching query does not exist."
        )
        self.assertEqual(logs.records[0].levelno, logging.ERROR)
