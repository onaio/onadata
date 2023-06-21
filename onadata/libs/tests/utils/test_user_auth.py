import pytz

from datetime import datetime
from unittest.mock import Mock, patch
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.user_auth import accept_project_invitation
from onadata.apps.logger.models import ProjectInvitation, Project
from onadata.libs.utils.user_auth import get_user_default_project
from onadata.libs.permissions import EditorRole, ManagerRole


class AcceptProjectInvitationTestCase(TestBase):
    """Tests for accept_project_inviation"""

    def setUp(self):
        super().setUp()
        self.bob = self._create_user("mike", "1234", True)
        self.project = get_user_default_project(self.bob)
        self.email = "janedoe@example.com"
        self.invitation = ProjectInvitation.objects.create(
            email=self.email,
            project=self.project,
            role="editor",
        )
        self.user.email = self.email
        self.user.save()
        self.mocked_now = datetime(2023, 6, 21, 14, 29, 0, tzinfo=pytz.utc)

    def test_accept_invitation(self):
        """Accept invitation works"""
        self.assertEqual(self.user.email, self.email)

        john_invitation = ProjectInvitation.objects.create(
            email="johndoe@example.com",
            project=self.project,
            role="manager",
        )
        project = Project.objects.create(
            name="Bob project 2",
            created_by=self.bob,
            organization=self.bob,
        )
        invitation = ProjectInvitation.objects.create(
            email=self.email,
            project=project,
            role="manager",
        )

        with patch("django.utils.timezone.now", Mock(return_value=self.mocked_now)):
            accept_project_invitation(self.invitation, self.user)
            self.invitation.refresh_from_db()
            self.assertEqual(self.invitation.status, ProjectInvitation.Status.ACCEPTED)
            self.assertEqual(self.invitation.accepted_at, self.mocked_now)
            self.assertTrue(EditorRole.user_has_role(self.user, self.project))
            # other invitations are not touched
            john_invitation.refresh_from_db()
            self.assertEqual(john_invitation.status, ProjectInvitation.Status.PENDING)
            # other projects are shared
            invitation.refresh_from_db()
            self.assertEqual(invitation.status, ProjectInvitation.Status.ACCEPTED)
            self.assertEqual(invitation.accepted_at, self.mocked_now)
            self.assertTrue(ManagerRole.user_has_role(self.user, project))

    def test_different_user_email(self):
        """Invitations accepted if user email is different from invitation email"""
        email = "nickiminaj@example.com"
        self.invitation.email = email
        self.invitation.save()

        self.assertNotEqual(self.user.email, self.invitation.email)

        project = Project.objects.create(
            name="Bob project 2",
            created_by=self.bob,
            organization=self.bob,
        )
        invitation = ProjectInvitation.objects.create(
            email=email,
            project=project,
            role="manager",
        )

        with patch("django.utils.timezone.now", Mock(return_value=self.mocked_now)):
            accept_project_invitation(self.invitation, self.user)
            self.invitation.refresh_from_db()
            self.assertEqual(self.invitation.status, ProjectInvitation.Status.ACCEPTED)
            self.assertEqual(self.invitation.accepted_at, self.mocked_now)
            self.assertTrue(EditorRole.user_has_role(self.user, self.project))
            # other projects are shared
            invitation.refresh_from_db()
            self.assertEqual(invitation.status, ProjectInvitation.Status.ACCEPTED)
            self.assertEqual(invitation.accepted_at, self.mocked_now)
            self.assertTrue(ManagerRole.user_has_role(self.user, project))

    def test_only_pending_accepted(self):
        """Only pending invitations are accepted"""
        self.invitation.status = ProjectInvitation.Status.REVOKED
        self.invitation.save()

        with patch("django.utils.timezone.now", Mock(return_value=self.mocked_now)):
            accept_project_invitation(self.invitation, self.user)
            self.invitation.refresh_from_db()
            self.assertEqual(self.invitation.status, ProjectInvitation.Status.REVOKED)
            self.assertIsNone(self.invitation.accepted_at)
            self.assertFalse(EditorRole.user_has_role(self.user, self.project))
