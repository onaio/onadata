import pytz
from datetime import datetime
from django.db import IntegrityError
from onadata.apps.logger.models import ProjectInvitation
from onadata.apps.main.tests.test_base import TestBase
from unittest.mock import patch, Mock
from onadata.libs.utils.user_auth import get_user_default_project


class ProjectInvitationTestCase(TestBase):
    """Tests for ProjectInvitation model"""

    def setUp(self) -> None:
        super().setUp()

        self.project = get_user_default_project(self.user)

    def test_creation(self):
        """We can create a ProjectInvitation object"""
        created_at = datetime(2023, 5, 17, 14, 21, 0, tzinfo=pytz.utc)
        resent_at = datetime(2023, 5, 17, 14, 24, 0, tzinfo=pytz.utc)
        accepted_at = datetime(2023, 5, 17, 14, 25, 0, tzinfo=pytz.utc)
        revoked_at = datetime(2023, 5, 17, 14, 26, 0, tzinfo=pytz.utc)

        with patch("django.utils.timezone.now", Mock(return_value=created_at)):
            invitation = ProjectInvitation.objects.create(
                email="janedoe@example.com",
                project=self.project,
                role="editor",
                status=ProjectInvitation.Status.REVOKED,
                accepted_at=accepted_at,
                resent_at=resent_at,
                revoked_at=revoked_at,
            )

        self.assertEqual(f"{invitation}", f"janedoe@example.com|{self.project}")
        self.assertEqual(invitation.email, "janedoe@example.com")
        self.assertEqual(invitation.project, self.project)
        self.assertEqual(invitation.role, "editor")
        self.assertEqual(invitation.status, ProjectInvitation.Status.REVOKED)
        self.assertEqual(invitation.created_at, created_at)
        self.assertEqual(invitation.accepted_at, accepted_at)
        self.assertEqual(invitation.resent_at, resent_at)
        self.assertEqual(invitation.revoked_at, revoked_at)

    def test_defaults(self):
        """Defaults for optional fields are correct"""
        invitation = ProjectInvitation.objects.create(
            email="janedoe@example.com",
            project=self.project,
            role="editor",
        )

        self.assertIsNone(invitation.accepted_at)
        self.assertIsNone(invitation.revoked_at)
        self.assertIsNone(invitation.resent_at)
        self.assertEqual(invitation.status, ProjectInvitation.Status.PENDING)

    def test_invitation_unique(self):
        """Duplicate entry with same email, project, status is not allowed"""
        ProjectInvitation.objects.create(
            email="janedoe@example.com",
            project=self.project,
            role="editor",
            status=ProjectInvitation.Status.REVOKED,
        )

        with self.assertRaises(IntegrityError):
            ProjectInvitation.objects.create(
                email="janedoe@example.com",
                project=self.project,
                role="readonly",
                status=ProjectInvitation.Status.REVOKED,
            )
