# -*- coding: utf-8 -*-
"""
email utility functions.
"""
import six
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import base36_to_int
from django.utils.crypto import constant_time_compare
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
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

    def check_token(self, invitation, token):
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
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        # Check that the timestamp/uid has not been tampered with
        if not constant_time_compare(
            self._make_token_with_timestamp(invitation, ts), token
        ):
            # RemovedInDjango40Warning: when the deprecation ends, replace
            # with:
            #   return False
            if not constant_time_compare(
                self._make_token_with_timestamp(invitation, ts, legacy=True),
                token,
            ):
                return False

        return True

    def make_token(self, invitation: ProjectInvitation) -> str:
        return super().make_token(invitation)

    def _make_hash_value(self, invitation, timestamp):
        return (
            six.text_type(invitation.pk)
            + six.text_type(timestamp)  # noqa W503
            + six.text_type(invitation.status)  # noqa W503
        )


class ProjectInvitationEmail(ProjectInvitationTokenGenerator):
    """
    A class to send a project invitation email
    """

    def __init__(self, invitation: ProjectInvitation) -> None:
        super().__init__()

        self.invitation = invitation

    def _get_url(self) -> str:
        """Returns the project invitation URL"""
        url = getattr(settings, "PROJECT_INVITATION_URL", None)
        # convert email to base 64
        emailb64 = urlsafe_base64_encode(force_bytes(self.invitation.email))
        token = self.make_token(self.invitation)
        query_params: dict[str, str] = {
            "invitation_id": emailb64,
            "invitation_token": token,
        }
        query_params_string = urlencode(query_params)

        return f"{url}?{query_params_string}"

    def send(self) -> None:
        """Send project invitation email"""
        message_path = "projects/invitation.txt"
        subject_path = "projects/invitation_subject.txt"
        deployment_name = getattr(settings, "DEPLOYMENT_NAME", "Ona")
        email_data = {
            "subject": render_to_string(
                subject_path, {"deployment_name": deployment_name}
            ),
            "message_txt": render_to_string(
                message_path,
                {
                    "deployment_name": deployment_name,
                    "project_name": self.invitation.project.name,
                    "invitation_url": self._get_url(),
                },
            ),
        }

        send_generic_email(self.invitation.email, **email_data)
