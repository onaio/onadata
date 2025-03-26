"""
Tests for ProjectInvitation model
"""

from datetime import datetime, timezone as tz
from unittest.mock import Mock, patch

from onadata.apps.logger.models import ProjectInvitation
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.user_auth import get_user_default_project


class ProjectInvitationTestCase(TestBase):
    """Tests for ProjectInvitation model"""

    def setUp(self) -> None:
        super().setUp()

        self.project = get_user_default_project(self.user)

    def test_creation(self):
        """We can create a ProjectInvitation object"""
        created_at = datetime(2023, 5, 17, 14, 21, 0, tzinfo=tz.utc)
        resent_at = datetime(2023, 5, 17, 14, 24, 0, tzinfo=tz.utc)
        accepted_at = datetime(2023, 5, 17, 14, 25, 0, tzinfo=tz.utc)
        revoked_at = datetime(2023, 5, 17, 14, 26, 0, tzinfo=tz.utc)
        jane = self._create_user("jane", "1234")

        with patch("django.utils.timezone.now", Mock(return_value=created_at)):
            invitation = ProjectInvitation.objects.create(
                email="janedoe@example.com",
                project=self.project,
                role="editor",
                status=ProjectInvitation.Status.ACCEPTED,
                accepted_at=accepted_at,
                resent_at=resent_at,
                revoked_at=revoked_at,
                invited_by=self.user,
                accepted_by=jane,
            )

        self.assertEqual(f"{invitation}", f"janedoe@example.com|{self.project}")
        self.assertEqual(invitation.email, "janedoe@example.com")
        self.assertEqual(invitation.project, self.project)
        self.assertEqual(invitation.role, "editor")
        self.assertEqual(invitation.status, ProjectInvitation.Status.ACCEPTED)
        self.assertEqual(invitation.created_at, created_at)
        self.assertEqual(invitation.accepted_at, accepted_at)
        self.assertEqual(invitation.resent_at, resent_at)
        self.assertEqual(invitation.revoked_at, revoked_at)
        self.assertEqual(invitation.invited_by, self.user)
        self.assertEqual(invitation.accepted_by, jane)

    def test_defaults(self):
        """Defaults for optional fields are correct"""
        invitation = ProjectInvitation.objects.create(
            email="janedoe@example.com",
            project=self.project,
            role="editor",
        )
        self.assertIsNone(invitation.invited_by)
        self.assertIsNone(invitation.accepted_by)
        self.assertIsNone(invitation.accepted_at)
        self.assertIsNone(invitation.revoked_at)
        self.assertIsNone(invitation.resent_at)
        self.assertEqual(invitation.status, ProjectInvitation.Status.PENDING)

    def test_revoke(self):
        """Calling revoke method works correctly"""
        mocked_now = datetime(2023, 5, 25, 11, 17, 0, tzinfo=tz.utc)

        with patch("django.utils.timezone.now", Mock(return_value=mocked_now)):
            invitation = ProjectInvitation.objects.create(
                email="janedoe@example.com",
                project=self.project,
                role="editor",
                status=ProjectInvitation.Status.PENDING,
            )
            invitation.revoke()
            invitation.refresh_from_db()
            self.assertEqual(invitation.revoked_at, mocked_now)
            self.assertEqual(invitation.status, ProjectInvitation.Status.REVOKED)

        # setting revoked_at explicitly works
        revoked_at = datetime(2023, 5, 10, 11, 17, 0, tzinfo=tz.utc)
        invitation = ProjectInvitation.objects.create(
            email="john@example.com",
            project=self.project,
            role="editor",
            status=ProjectInvitation.Status.PENDING,
        )
        invitation.revoke(revoked_at=revoked_at)
        invitation.refresh_from_db()
        self.assertEqual(invitation.revoked_at, revoked_at)
        self.assertEqual(invitation.status, ProjectInvitation.Status.REVOKED)

    def test_accept(self):
        """Calling accept method works correctly"""
        mocked_now = datetime(2023, 5, 25, 11, 17, 0, tzinfo=tz.utc)
        jane = self._create_user("jane", "1234")

        with patch("django.utils.timezone.now", Mock(return_value=mocked_now)):
            invitation = ProjectInvitation.objects.create(
                email="janedoe@example.com",
                project=self.project,
                role="editor",
                status=ProjectInvitation.Status.PENDING,
            )
            invitation.accept()
            invitation.refresh_from_db()
            self.assertEqual(invitation.accepted_at, mocked_now)
            self.assertIsNone(invitation.accepted_by)
            self.assertEqual(invitation.status, ProjectInvitation.Status.ACCEPTED)

        # setting accepted_at explicitly works
        accepted_at = datetime(2023, 5, 10, 11, 17, 0, tzinfo=tz.utc)
        invitation = ProjectInvitation.objects.create(
            email="john@example.com",
            project=self.project,
            role="editor",
            status=ProjectInvitation.Status.PENDING,
        )
        invitation.accept(accepted_at=accepted_at, accepted_by=jane)
        invitation.refresh_from_db()
        self.assertEqual(invitation.accepted_at, accepted_at)
        self.assertEqual(invitation.accepted_by, jane)
        self.assertEqual(invitation.status, ProjectInvitation.Status.ACCEPTED)
