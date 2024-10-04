"""Tests for module onadata.apps.api.tasks"""

import sys

from unittest.mock import patch

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.db import DatabaseError, OperationalError

from onadata.apps.api.tasks import (
    send_project_invitation_email_async,
    regenerate_form_instance_json,
    share_project_async,
    ShareProject,
)
from onadata.apps.logger.models import ProjectInvitation, Instance
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import ManagerRole
from onadata.libs.serializers.organization_serializer import OrganizationSerializer
from onadata.libs.utils.user_auth import get_user_default_project
from onadata.libs.utils.email import ProjectInvitationEmail
from onadata.libs.utils.cache_tools import ORG_PROFILE_CACHE

User = get_user_model()


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

        def mock_get_full_dict(
            self, include_related=True
        ):  # pylint: disable=unused-argument
            return {}

        with patch.object(Instance, "get_full_dict", mock_get_full_dict):
            self._publish_transportation_form_and_submit_instance()

        cache_key = f"xfm-regenerate_instance_json_task-{self.xform.pk}"
        cache.set(cache_key, "foo")
        instance = self.xform.instances.first()
        self.assertFalse(instance.json)
        self.assertFalse(self.xform.is_instance_json_regenerated)
        regenerate_form_instance_json.delay(self.xform.pk)
        instance.refresh_from_db()
        self.assertTrue(instance.json)
        self.xform.refresh_from_db()
        self.assertTrue(self.xform.is_instance_json_regenerated)
        # task_id stored in cache should be deleted
        self.assertIsNone(cache.get(cache_key))

    def test_json_overriden(self):
        """Existing json is overriden"""

        def mock_get_full_dict(
            self, include_related=True
        ):  # pylint: disable=unused-argument
            return {"foo": "bar"}

        with patch.object(Instance, "get_full_dict", mock_get_full_dict):
            self._publish_transportation_form_and_submit_instance()

        instance = self.xform.instances.first()
        self.assertEqual(instance.json.get("foo"), "bar")
        regenerate_form_instance_json.delay(self.xform.pk)
        instance.refresh_from_db()
        self.assertFalse("foo" in instance.json)

    @patch("onadata.apps.api.tasks.logger.exception")
    def test_form_id_invalid(self, mock_log_exception):
        """An invalid xform_id is handled"""

        regenerate_form_instance_json.delay(sys.maxsize)

        mock_log_exception.assert_called_once()

    def test_already_generated(self):
        """Regeneration fails for a form whose regeneration has already been done"""

        def mock_get_full_dict(
            self, include_related=True
        ):  # pylint: disable=unused-argument
            return {}

        with patch.object(Instance, "get_full_dict", mock_get_full_dict):
            self._publish_transportation_form_and_submit_instance()

        self.xform.is_instance_json_regenerated = True
        self.xform.save()
        instance = self.xform.instances.first()
        self.assertFalse(instance.json)
        self.assertTrue(self.xform.is_instance_json_regenerated)
        regenerate_form_instance_json.delay(self.xform.pk)
        instance.refresh_from_db()
        self.assertFalse(instance.json)


def set_cache_for_org(org, request):
    """Utility to set org cache"""
    org_profile_json = OrganizationSerializer(org, context={"request": request}).data
    cache.set(f"{ORG_PROFILE_CACHE}{org.user.username}-owner", org_profile_json)


class ShareProjectAsyncTestCase(TestBase):
    """Tests for share_project_async"""

    def setUp(self):
        super().setUp()

        self._publish_transportation_form()
        self.alice = self._create_user("alice", "Yuao8(-)")

    def test_share(self):
        """Project is shared with user"""
        share_project_async.delay(self.project.id, "alice", "manager")

        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))

    def test_remove(self):
        """User is removed from project"""
        # Add user to project
        ManagerRole.add(self.alice, self.project)
        # Remove user
        share_project_async.delay(self.project.id, "alice", "manager", True)

        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))

    @patch("onadata.apps.api.tasks.logger.exception")
    def test_invalid_project_id(self, mock_log):
        """Invalid projecct_id is handled"""
        share_project_async.delay(sys.maxsize, "alice", "manager")
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))
        mock_log.assert_called_once()

    @patch.object(ShareProject, "save")
    @patch("onadata.apps.api.tasks.share_project_async.retry")
    def test_database_error(self, mock_retry, mock_share):
        """We retry calls if DatabaseError is raised"""
        mock_share.side_effect = DatabaseError()
        share_project_async.delay(self.project.id, self.user.pk, "manager")
        self.assertTrue(mock_retry.called)
        _, kwargs = mock_retry.call_args_list[0]
        self.assertTrue(isinstance(kwargs["exc"], DatabaseError))

    @patch.object(ShareProject, "save")
    @patch("onadata.apps.api.tasks.share_project_async.retry")
    def test_connection_error(self, mock_retry, mock_share):
        """We retry calls if ConnectionError is raised"""
        mock_share.side_effect = ConnectionError()
        share_project_async.delay(self.project.pk, self.user.pk, "manager")
        self.assertTrue(mock_retry.called)
        _, kwargs = mock_retry.call_args_list[0]
        self.assertTrue(isinstance(kwargs["exc"], ConnectionError))

    @patch.object(ShareProject, "save")
    @patch("onadata.apps.api.tasks.share_project_async.retry")
    def test_operation_error(self, mock_retry, mock_share):
        """We retry calls if OperationError is raised"""
        mock_share.side_effect = OperationalError()
        share_project_async.delay(self.project.pk, self.user.pk, "manager")
        self.assertTrue(mock_retry.called)
        _, kwargs = mock_retry.call_args_list[0]
        self.assertTrue(isinstance(kwargs["exc"], OperationalError))
