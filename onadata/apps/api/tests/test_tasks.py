"""Tests for module onadata.apps.api.tasks"""

from unittest.mock import patch

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.api.tasks import (
    send_project_invitation_email_async,
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
