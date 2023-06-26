"""Tests for module onadata.apps.api.tasks"""

from unittest.mock import patch

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.api.tasks import (
    send_project_invitation_email_async,
    accept_project_invitation_async,
)
from onadata.apps.logger.models import ProjectInvitation
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


class AcceptProjectInvitationTesCase(TestBase):
    """Tests for accept_project_invitation_async"""

    def setUp(self):
        super().setUp()

        project = get_user_default_project(self.user)
        self.invitation = ProjectInvitation.objects.create(
            project=project,
            email="janedoe@example.com",
            role="manager",
        )

    @patch("onadata.apps.api.tasks.accept_project_invitation")
    def test_accept_invitation(self, mock_accept_invitation):
        """Test invitation is accepted"""
        accept_project_invitation_async(self.invitation.id, self.user.id)
        mock_accept_invitation.assert_called_once_with(self.invitation, self.user)
