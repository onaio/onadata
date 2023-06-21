from six.moves.urllib.parse import urlencode
from mock import patch
from django.utils.http import urlsafe_base64_encode
from django.test import RequestFactory
from django.test.utils import override_settings
from django.utils.encoding import force_bytes
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.email import (
    get_verification_email_data,
    get_verification_url,
    get_project_invitation_url,
)
from onadata.libs.utils.email import ProjectInvitationEmail
from onadata.apps.logger.models import ProjectInvitation
from onadata.libs.utils.user_auth import get_user_default_project


VERIFICATION_URL = "http://ab.cd.ef"


class TestEmail(TestBase):
    def setUp(self):
        self.email = "john@doe.com"
        self.username = ("johndoe",)
        self.verification_key = "123abc"
        self.redirect_url = "http://red.ir.ect"
        self.custom_request = RequestFactory().get("/path", data={"name": "test"})

    @override_settings(VERIFICATION_URL=None)
    def test_get_verification_url(self):
        # without redirect_url
        verification_url = get_verification_url(
            **{
                "redirect_url": None,
                "request": self.custom_request,
                "verification_key": self.verification_key,
            }
        )

        self.assertEqual(
            verification_url,
            (
                "http://testserver/api/v1/profiles/verify_email?"
                "verification_key=%s" % self.verification_key
            ),
        )

        # with redirect_url
        verification_url = get_verification_url(
            **{
                "redirect_url": self.redirect_url,
                "request": self.custom_request,
                "verification_key": self.verification_key,
            }
        )

        string_query_params = urlencode(
            {
                "verification_key": self.verification_key,
                "redirect_url": self.redirect_url,
            }
        )

        self.assertEqual(
            verification_url,
            ("http://testserver/api/v1/profiles/verify_email?%s" % string_query_params),
        )

    def _get_email_data(self, include_redirect_url=False):
        verification_url = get_verification_url(
            **{
                "redirect_url": include_redirect_url and self.redirect_url,
                "request": self.custom_request,
                "verification_key": self.verification_key,
            }
        )

        email_data = get_verification_email_data(
            **{
                "email": self.email,
                "username": self.username,
                "verification_url": verification_url,
                "request": self.custom_request,
            }
        )

        self.assertIn("email", email_data)
        self.assertIn(self.email, email_data.get("email"))
        self.assertIn("subject", email_data)
        self.assertIn("message_txt", email_data)

        return email_data

    @override_settings(VERIFICATION_URL=None)
    def test_get_verification_email_data_without_verification_url_set(self):
        email_data = self._get_email_data()
        self.assertIn(
            (
                "http://testserver/api/v1/profiles/verify_email?"
                "verification_key=%s" % self.verification_key
            ),
            email_data.get("message_txt"),
        )

    @override_settings(VERIFICATION_URL=VERIFICATION_URL)
    def test_get_verification_email_data_with_verification_url_set(self):
        email_data = self._get_email_data()
        self.assertIn(
            "{}?verification_key={}".format(VERIFICATION_URL, self.verification_key),
            email_data.get("message_txt"),
        )

    @override_settings(VERIFICATION_URL=VERIFICATION_URL)
    def test_get_verification_email_data_with_verification_and_redirect_urls(self):
        email_data = self._get_email_data(include_redirect_url=True)
        encoded_url = urlencode(
            {
                "verification_key": self.verification_key,
                "redirect_url": self.redirect_url,
            }
        )
        self.assertIn(encoded_url.replace("&", "&amp;"), email_data.get("message_txt"))

    def test_email_data_does_not_contain_newline_chars(self):
        email_data = self._get_email_data(include_redirect_url=True)
        self.assertNotIn("\n", email_data.get("subject"))


class ProjectInvitationEmailTestCase(TestBase):
    """Tests for class ProjectInvitationEmail"""

    def setUp(self) -> None:
        super().setUp()

        self.project = get_user_default_project(self.user)
        self.project.name = "Test Invitation"
        self.project.save()
        self.invitation = ProjectInvitation.objects.create(
            email="janedoe@example.com",
            project=self.project,
            role="editor",
            status=ProjectInvitation.Status.PENDING,
        )
        self.email = ProjectInvitationEmail(
            self.invitation, "https://example.com/register"
        )

    def _mock_invitation_make_token(self):
        return "tokenmoto"

    @patch.object(ProjectInvitationEmail, "make_token", _mock_invitation_make_token)
    @patch("onadata.libs.utils.email.urlsafe_base64_encode")
    def test_make_url(self, mock_base64_encode):
        """The invitation link created is correct"""
        mock_base64_encode.return_value = "idbase64"
        link = (
            "https://example.com/register?"
            "invitation_id=idbase64&invitation_token=tokenmoto"
        )
        self.assertEqual(self.email.make_url(), link)

    @override_settings(DEPLOYMENT_NAME="Misfit")
    @patch.object(ProjectInvitationEmail, "make_token", _mock_invitation_make_token)
    @patch("onadata.libs.utils.email.urlsafe_base64_encode")
    @patch("onadata.libs.utils.email.send_generic_email")
    def test_send(self, mock_send, mock_base64_encode):
        """Email is sent successfully"""
        mock_base64_encode.return_value = "idbase64"
        self.email.send()
        email_data = {
            "subject": "Invitation to Join a Project on Misfit",
            "message_txt": "\nHello,\n\nYou have been added to Test Invitation by"
            " a project admin allowing you to begin data collection.\n\nTo begin"
            " using Misfit, please create an account first by clicking the link below:"
            "\nhttps://example.com/register?invitation_id=idbase64&amp;invitation_token=tokenmoto"
            "\n\nThanks,\nThe Team at Misfit\n",
        }
        mock_send.assert_called_with(
            self.invitation.email,
            **email_data,
        )

    def test_check_invitation(self):
        """Check invitation works correctly"""
        # valid invitation_id and token passes
        token = self.email.make_token()
        invitation_id = urlsafe_base64_encode(force_bytes(self.invitation.id))
        check = ProjectInvitationEmail.check_invitation(invitation_id, token)
        self.assertEqual(self.invitation, check)
        # invalid id does not pass
        check = ProjectInvitationEmail.check_invitation("foo", token)
        self.assertIsNone(check)
        # invalid token does not pass
        check = ProjectInvitationEmail.check_invitation(invitation_id, "sometoken")
        self.assertIsNone(check)


class ProjectInvitationURLTestCase(TestBase):
    """Tests for get_project_invitation_url"""

    def setUp(self):
        super().setUp()

        self.custom_request = RequestFactory().get("/path", data={"name": "test"})

    @override_settings(PROJECT_INVITATION_URL="https://example.com/register")
    def test_url_configured(self):
        """settings.PROJECT_INVITATION_URL is set"""
        url = get_project_invitation_url(self.custom_request)
        self.assertEqual(url, "https://example.com/register")

    def test_url_not_configured(self):
        """settings.PROJECT_INVITATION_URL not set"""
        url = get_project_invitation_url(self.custom_request)
        self.assertEqual(url, "http://testserver/api/v1/profiles")
