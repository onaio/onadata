# -*- coding: utf-8 -*-
"""
Test onadata.utils.emails module.
"""
from unittest.mock import patch

from django.test import RequestFactory
from django.test.utils import override_settings

from six.moves.urllib.parse import urlencode

from onadata.apps.logger.models import ProjectInvitation
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.email import (
    ProjectInvitationEmail,
    get_project_invitation_url,
    get_verification_email_data,
    get_verification_url,
)
from onadata.libs.utils.user_auth import get_user_default_project

VERIFICATION_URL = "http://ab.cd.ef"


class TestEmail(TestBase):
    """Test onadata.utils.email module"""

    def setUp(self):
        self.email = "john@doe.com"
        self.username = ("johndoe",)
        self.verification_key = "123abc"
        self.redirect_url = "http://red.ir.ect"
        self.custom_request = RequestFactory().get("/path", data={"name": "test"})

    @override_settings(
        VERIFICATION_URL={
            "stage-testserver": "https://stage-testserver/email-verification-confirmation",
            "*": None,
        }
    )
    @override_settings(ALLOWED_HOSTS="*")
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

        # with redirect_url
        self.custom_request.META["HTTP_HOST"] = "stage-testserver"
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
            (
                "https://stage-testserver/email-verification-confirmation?%s"
                % string_query_params
            ),
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

    @override_settings(VERIFICATION_URL={"*": VERIFICATION_URL})
    def test_get_verification_email_data_with_verification_url_set(self):
        email_data = self._get_email_data()
        self.assertIn(
            "{}?verification_key={}".format(VERIFICATION_URL, self.verification_key),
            email_data.get("message_txt"),
        )

    @override_settings(VERIFICATION_URL={"*": VERIFICATION_URL})
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


@override_settings(DEFAULT_FROM_EMAIL="no-reply@mail.misfit.com")
class ProjectInvitationEmailTestCase(TestBase):
    """Tests for class ProjectInvitationEmail"""

    def setUp(self) -> None:
        super().setUp()

        self.project = get_user_default_project(self.user)
        self.user.profile.name = "Test User"
        self.user.profile.save()
        self.project.name = "Test Invitation"
        self.project.save()
        self.user.email = "user@foo.com"
        self.user.save()
        self.invitation = ProjectInvitation.objects.create(
            email="janedoe@example.com",
            project=self.project,
            role="editor",
            status=ProjectInvitation.Status.PENDING,
            invited_by=self.user,
        )
        self.email = ProjectInvitationEmail(
            self.invitation, "https://example.com/register"
        )

    @override_settings(DEPLOYMENT_NAME="Misfit")
    @patch("onadata.libs.utils.email.send_mail")
    def test_send(self, mock_send):
        """Email is sent successfully"""
        self.email.send()
        expected_subject = "Invitation to Join a Project on Misfit"
        expected_message = (
            "\nHello,\n"
            "You have been added to Test Invitation by a project admin allowing"
            " you to begin data collection.\n"
            "To begin using Misfit, please create an account first by"
            " clicking the link below:\n"
            "https://example.com/register\n"
            "Thanks,\nThe Team at Misfit\n"
        )
        expected_html_message = (
            "\n<p>Hello,</p>\n<p>You have been added to Test Invitation by a project"
            " admin allowing you to begin data collection.</p>\n"
            "<p>To begin using Misfit, please create an account first by"
            " clicking the link below:</p>\n"
            "<p><a href='https://example.com/register'>https://example.com/register</a></p>\n"
            "<p>Thanks,</p>\n<p>The Team at Misfit</p>\n"
        )
        mock_send.assert_called_with(
            expected_subject,
            expected_message,
            "no-reply@mail.misfit.com",
            (self.invitation.email,),
            html_message=expected_html_message,
        )

    @override_settings(DEPLOYMENT_NAME="Misfit")
    def test_get_template_data(self):
        """Context data for the email templates is correct"""
        expected_data = {
            "subject": {"deployment_name": "Misfit"},
            "body": {
                "deployment_name": "Misfit",
                "project_name": "Test Invitation",
                "invitation_url": "https://example.com/register",
                "organization": "Test User",
                "invited_by": "user@foo.com",
                "username": "janedoe@example.com",
            },
        }
        data = self.email.get_template_data()
        self.assertEqual(data, expected_data)

        # invitation invited_by is null
        self.invitation.invited_by = None
        self.invitation.save()
        expected_data = {
            "subject": {"deployment_name": "Misfit"},
            "body": {
                "deployment_name": "Misfit",
                "project_name": "Test Invitation",
                "invitation_url": "https://example.com/register",
                "organization": "Test User",
                "invited_by": None,
                "username": "janedoe@example.com",
            },
        }
        data = self.email.get_template_data()
        self.assertEqual(data, expected_data)

    @override_settings(
        DEPLOYMENT_NAME="Misfit",
        PROJECT_INVITATION_SUBJECT="Invitation to join {deployment_name}",
        PROJECT_INVITATION_MESSAGE=(
            "<p>Hello {username}</p>"
            "<p>You have been added to {project_name} in the"
            " {organization} account on Misfit.</p>"
            "<p>To begin using Misfit, please verify your account"
            " first by clicking the link below:</p>"
            "<p>{invitation_url}</p>"
            "<p>Then, enter you first and last name, desired username,"
            " and password and click Join. Once complete, please notify"
            " your project admin {invited_by} and we'll activate your account.</p>"
        ),
    )
    @patch("onadata.libs.utils.email.send_mail")
    def test_send_custom_message(self, mock_send):
        """Custom subject and message works"""
        self.email.send()
        expected_subject = "Invitation to join Misfit"
        expected_message = (
            "Hello janedoe@example.com"
            "You have been added to Test Invitation in the"
            " Test User account on Misfit."
            "To begin using Misfit, please verify your account"
            " first by clicking the link below:"
            "https://example.com/register"
            "Then, enter you first and last name, desired username,"
            " and password and click Join. Once complete, please notify"
            " your project admin user@foo.com and we'll activate your account."
        )
        expected_html_message = (
            "<p>Hello janedoe@example.com</p>"
            "<p>You have been added to Test Invitation in the"
            " Test User account on Misfit.</p>"
            "<p>To begin using Misfit, please verify your account"
            " first by clicking the link below:</p>"
            "<p>https://example.com/register</p>"
            "<p>Then, enter you first and last name, desired username,"
            " and password and click Join. Once complete, please notify"
            " your project admin user@foo.com and we'll activate your account.</p>"
        )
        mock_send.assert_called_with(
            expected_subject,
            expected_message,
            "no-reply@mail.misfit.com",
            (self.invitation.email,),
            html_message=expected_html_message,
        )


class ProjectInvitationURLTestCase(TestBase):
    """Tests for get_project_invitation_url"""

    def setUp(self):
        super().setUp()

        self.custom_request = RequestFactory().get("/path", data={"name": "test"})

    @override_settings(PROJECT_INVITATION_URL={"*": "https://example.com/register"})
    def test_url_configured(self):
        """settings.PROJECT_INVITATION_URL is set"""
        url = get_project_invitation_url(self.custom_request)
        self.assertEqual(url, "https://example.com/register")

    @override_settings(
        PROJECT_INVITATION_URL={
            "*": "https://example.com/register",
            "new-domain.com": "https://new-domain.com/register",
        }
    )
    @override_settings(ALLOWED_HOSTS=["*"])
    def test_url_configured_for_host(self):
        """settings.PROJECT_INVITATION_URL is set for specific host"""
        self.custom_request.META["HTTP_HOST"] = "new-domain.com"
        url = get_project_invitation_url(self.custom_request)
        self.assertEqual(url, "https://new-domain.com/register")

    def test_url_not_configured(self):
        """settings.PROJECT_INVITATION_URL not set"""
        url = get_project_invitation_url(self.custom_request)
        self.assertEqual(url, "http://testserver/api/v1/profiles")
