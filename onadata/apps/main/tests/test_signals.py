"""Tests for onadata.apps.main.signals module"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model

from onadata.apps.logger.models import Project, ProjectInvitation
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import EditorRole, ManagerRole
from onadata.libs.utils.user_auth import get_user_default_project

User = get_user_model()


class AcceptProjectInvitationTestCase(TestBase):
    """Tests for accept_project_inviation"""

    def setUp(self):
        super().setUp()
        self.project = get_user_default_project(self.user)
        self.invitation = ProjectInvitation.objects.create(
            email="mike@example.com",
            project=self.project,
            role="editor",
        )
        self.mocked_now = datetime(2023, 6, 21, 14, 29, 0, tzinfo=timezone.utc)

    def test_accept_invitation(self):
        """Accept invitation works"""
        john_invitation = ProjectInvitation.objects.create(
            email="johndoe@example.com",
            project=self.project,
            role="manager",
        )
        project = Project.objects.create(
            name="Project 2",
            created_by=self.user,
            organization=self.user,
        )
        mike_invitation = ProjectInvitation.objects.create(
            email="mike@example.com",
            project=project,
            role="manager",
        )

        with patch("django.utils.timezone.now", Mock(return_value=self.mocked_now)):
            mike = User.objects.create(username="mike", email="mike@example.com")
            self.invitation.refresh_from_db()
            self.assertEqual(self.invitation.status, ProjectInvitation.Status.ACCEPTED)
            self.assertEqual(self.invitation.accepted_at, self.mocked_now)
            self.assertEqual(self.invitation.accepted_by, mike)
            self.assertTrue(EditorRole.user_has_role(mike, self.project))
            # other invitations are not touched
            john_invitation.refresh_from_db()
            self.assertEqual(john_invitation.status, ProjectInvitation.Status.PENDING)
            # other projects are shared
            mike_invitation.refresh_from_db()
            self.assertEqual(mike_invitation.status, ProjectInvitation.Status.ACCEPTED)
            self.assertEqual(mike_invitation.accepted_at, self.mocked_now)
            self.assertEqual(mike_invitation.accepted_by, mike)
            self.assertTrue(ManagerRole.user_has_role(mike, project))

    def test_only_pending_accepted(self):
        """Only pending invitations are accepted"""
        self.invitation.status = ProjectInvitation.Status.REVOKED
        self.invitation.save()

        with patch("django.utils.timezone.now", Mock(return_value=self.mocked_now)):
            mike = User.objects.create(username="mike", email="mike@example.com")
            self.invitation.refresh_from_db()
            self.assertEqual(self.invitation.status, ProjectInvitation.Status.REVOKED)
            self.assertIsNone(self.invitation.accepted_at)
            self.assertIsNone(self.invitation.accepted_by)
            self.assertFalse(EditorRole.user_has_role(mike, self.project))
