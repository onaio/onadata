# -*- coding: utf-8 -*-
"""
email utility functions.
"""
from typing import Optional
import six
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.http import HttpRequest
from django.utils.http import (
    base36_to_int,
    urlsafe_base64_encode,
    urlsafe_base64_decode,
)
from django.utils.crypto import constant_time_compare
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from six.moves.urllib.parse import urlencode
from rest_framework.reverse import reverse
from onadata.apps.logger.models import ProjectInvitation


def get_verification_url(redirect_url, request, verification_key):
    """Returns the verification_url"""
    verification_url = getattr(settings, "VERIFICATION_URL", None)
    url = verification_url or reverse("userprofile-verify-email", request=request)
    query_params_dict = {"verification_key": verification_key}
    if redirect_url:
        query_params_dict.update({"redirect_url": redirect_url})
    query_params_string = urlencode(query_params_dict)
    verification_url = f"{url}?{query_params_string}"

    return verification_url


def get_verification_email_data(email, username, verification_url, request):
    """
    Returns the verification email content
    """
    email_data = {"email": email}

    ctx_dict = {
        "username": username,
        "expiration_days": getattr(settings, "ACCOUNT_ACTIVATION_DAYS", 1),
        "verification_url": verification_url,
    }

    key_template_path_dict = {
        "subject": "registration/verification_email_subject.txt",
        "message_txt": "registration/verification_email.txt",
    }
    for key, template_path in key_template_path_dict.items():
        email_data.update(
            {key: render_to_string(template_path, ctx_dict, request=request)}
        )

    return email_data


def get_account_lockout_email_data(username, ip_address, end=False):
    """Generates both the email upon start and end of account lockout"""
    message_path = "account_lockout/lockout_start.txt"
    subject_path = "account_lockout/lockout_email_subject.txt"
    if end:
        message_path = "account_lockout/lockout_end.txt"
    ctx_dict = {
        "username": username,
        "remote_ip": ip_address,
        "lockout_time": getattr(settings, "LOCKOUT_TIME", 1800) / 60,
        "support_email": getattr(settings, "SUPPORT_EMAIL", "support@example.com"),
    }

    email_data = {
        "subject": render_to_string(subject_path),
        "message_txt": render_to_string(message_path, ctx_dict),
    }

    return email_data


def send_generic_email(email, message_txt, subject):
    if any(a in [None, ""] for a in [email, message_txt, subject]):
        raise ValueError("email, message_txt amd subject arguments are ALL required.")

    from_email = settings.DEFAULT_FROM_EMAIL
    email_message = EmailMultiAlternatives(subject, message_txt, from_email, [email])

    email_message.send()


class ProjectInvitationTokenGenerator(PasswordResetTokenGenerator):
    """Strategy object for generating and checking tokens for project invitation URL"""

    def check_token(self, invitation, token):  # pylint: disable=arguments-renamed
        """
        Check that a project invitation token is correct for a given user.
        """
        if not (invitation and token):
            return False
        # Parse the token
        try:
            ts_b36, _ = token.split("-")
        except ValueError:
            return False

        try:
            ts = base36_to_int(ts_b36)  # pylint: disable=invalid-name
        except ValueError:
            return False

        # Check that the timestamp/uid has not been tampered with
        if not constant_time_compare(
            self._make_token_with_timestamp(  # pylint: disable=no-value-for-parameter
                invitation, ts
            ),
            token,
        ):
            # RemovedInDjango40Warning: when the deprecation ends, replace
            # with:
            #   return False
            if not constant_time_compare(
                self._make_token_with_timestamp(  # pylint: disable=unexpected-keyword-arg
                    invitation,
                    ts,
                    legacy=True,
                ),  # pylint: disable=no-value-for-parameter
                token,
            ):
                return False

        return True

    def _make_hash_value(  # pylint: disable=arguments-renamed
        self,
        invitation,
        timestamp,
    ):
        """Make a hash value for the invitation token

        The  hash is made up of:

        1. primary key of the invitation - will uniquely identify the
        hash as belonging to a particular inivtation
        2. timestamp - the current timestamp
        3. invitation status - will invaliddate the link when the status
        changes. If an invitation with a status of pending changes to accepted,
        the link will be invalidated and cannot be re-used
        """
        return (
            six.text_type(invitation.pk)
            + six.text_type(timestamp)  # noqa W503
            + six.text_type(invitation.status)  # noqa W503
        )


def get_project_invitation_url(request: HttpRequest):
    """Get project invitation url"""
    url: str = getattr(settings, "PROJECT_INVITATION_URL", "")

    if not url:
        url = reverse("userprofile-list", request=request)

    return url


class ProjectInvitationEmail(ProjectInvitationTokenGenerator):
    """
    A class to send a project invitation email
    """

    def __init__(self, invitation: ProjectInvitation, url: str) -> None:
        super().__init__()

        self.invitation = invitation
        self.url = url

    def _make_token(self) -> str:
        return super().make_token(self.invitation)

    @staticmethod
    def check_invitation(encoded_id: str, token: str) -> Optional[ProjectInvitation]:
        """Check if an invitation is valid"""
        try:
            invitation_id = int(urlsafe_base64_decode(encoded_id))

        except ValueError:
            return None

        try:
            invitation = ProjectInvitation.objects.get(pk=invitation_id)

        except ProjectInvitation.DoesNotExist:
            return None

        if ProjectInvitationTokenGenerator().check_token(invitation, token):
            return invitation

        return None

    def make_url(self) -> str:
        """Returns the project invitation URL to be embedded in the email"""
        query_params: dict[str, str] = {
            "invitation_id": urlsafe_base64_encode(force_bytes(self.invitation.id)),
            "invitation_token": self._make_token(),
        }
        query_params_string = urlencode(query_params)

        return f"{self.url}?{query_params_string}"

    def get_template_data(self) -> dict[str, str]:
        """Get context data for the templates"""
        deployment_name = getattr(settings, "DEPLOYMENT_NAME", "Ona")
        organization = self.invitation.project.organization.profile.name
        data = {
            "subject": {"deployment_name": deployment_name},
            "body": {
                "deployment_name": deployment_name,
                "project_name": self.invitation.project.name,
                "invitation_url": self.make_url(),
                "organization": organization,
            },
        }

        return data

    def get_email_data(self) -> dict[str, str]:
        """Get the email data to be sent"""
        message_path = "projects/invitation.txt"
        subject_path = "projects/invitation_subject.txt"
        template_data = self.get_template_data()
        email_data = {
            "subject": render_to_string(subject_path, template_data["subject"]),
            "message_txt": render_to_string(
                message_path,
                template_data["body"],
            ),
        }
        return email_data

    def send(self) -> None:
        """Send project invitation email"""
        send_generic_email(self.invitation.email, **self.get_email_data())
