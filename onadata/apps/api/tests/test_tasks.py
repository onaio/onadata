"""Tests for module onadata.apps.api.tasks"""

import sys

from unittest.mock import patch

from django.core.cache import cache
from django.contrib.auth import get_user_model

from onadata.apps.api.tasks import (
    send_project_invitation_email_async,
    regenerate_form_instance_json,
    add_org_user_and_share_projects_async,
    remove_org_user_async,
)
from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.logger.models import ProjectInvitation, Instance
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.user_auth import get_user_default_project
from onadata.libs.utils.email import ProjectInvitationEmail

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


@patch("onadata.apps.api.tasks.tools.add_org_user_and_share_projects")
class AddOrgUserAndShareProjectsAsyncTestCase(TestBase):
    """Tests for add_org_user_and_share_projects_async"""

    def setUp(self):
        super().setUp()

        self.org_user = User.objects.create(username="onaorg")
        alice = self._create_user("alice", "1234&&")
        self.org = OrganizationProfile.objects.create(
            user=self.org_user, name="Ona Org", creator=alice
        )

    def test_user_added_to_org(self, mock_add):
        """User is added to organization"""
        add_org_user_and_share_projects_async(self.org.pk, self.user.pk, "manager")
        mock_add.assert_called_once_with(self.org, self.user, "manager")

    def test_role_optional(self, mock_add):
        """role param is optional"""
        add_org_user_and_share_projects_async(self.org.pk, self.user.pk)
        mock_add.assert_called_once_with(self.org, self.user, None)

    @patch("onadata.apps.api.tasks.logger.exception")
    def test_invalid_org_id(self, mock_log, mock_add):
        """Invalid org_id is handled"""
        add_org_user_and_share_projects_async(sys.maxsize, self.user.pk)
        mock_add.assert_not_called()
        mock_log.assert_called_once()

    @patch("onadata.apps.api.tasks.logger.exception")
    def test_invalid_user_id(self, mock_log, mock_add):
        """Invalid org_id is handled"""
        add_org_user_and_share_projects_async(self.org.pk, sys.maxsize)
        mock_add.assert_not_called()
        mock_log.assert_called_once()


@patch("onadata.apps.api.tasks.tools.remove_user_from_organization")
class RemoveOrgUserAsyncTestCase(TestBase):
    """Tests for remove_org_user_async"""

    def setUp(self):
        super().setUp()

        self.org_user = User.objects.create(username="onaorg")
        alice = self._create_user("alice", "1234&&")
        self.org = OrganizationProfile.objects.create(
            user=self.org_user, name="Ona Org", creator=alice
        )

    def test_user_removed_from_org(self, mock_remove):
        """User is removed from organization"""
        remove_org_user_async(self.org.pk, self.user.pk)
        mock_remove.assert_called_once_with(self.org, self.user)

    @patch("onadata.apps.api.tasks.logger.exception")
    def test_invalid_org_id(self, mock_log, mock_remove):
        """Invalid org_id is handled"""
        remove_org_user_async(sys.maxsize, self.user.pk)
        mock_remove.assert_not_called()
        mock_log.assert_called_once()

    @patch("onadata.apps.api.tasks.logger.exception")
    def test_invalid_user_id(self, mock_log, mock_remove):
        """Invalid org_id is handled"""
        remove_org_user_async(self.org.pk, sys.maxsize)
        mock_remove.assert_not_called()
        mock_log.assert_called_once()
