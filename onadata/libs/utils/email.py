# -*- coding: utf-8 -*-
"""
Email utility functions.
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.http import HttpRequest
from django.utils.html import strip_tags
from django.template.loader import render_to_string
from six.moves.urllib.parse import urlencode
from rest_framework.reverse import reverse
from onadata.apps.logger.models import ProjectInvitation


def get_verification_url(redirect_url, request, verification_key):
    """Returns the verification_url"""
    # get verification URL based on host
    verification_url_map = getattr(settings, "VERIFICATION_URL", {})
    host = request.get_host()
    url = (
        (
            verification_url_map
            and host in verification_url_map
            and verification_url_map[host]
        )
        or (
            verification_url_map
            and "*" in verification_url_map
            and verification_url_map["*"]
        )
        or reverse("userprofile-verify-email", request=request)
    )
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
    """Sends an email."""
    if any(a in [None, ""] for a in [email, message_txt, subject]):
        raise ValueError("email, message_txt amd subject arguments are ALL required.")

    from_email = settings.DEFAULT_FROM_EMAIL
    email_message = EmailMultiAlternatives(subject, message_txt, from_email, [email])

    email_message.send()


def get_project_invitation_url(request: HttpRequest):
    """Get project invitation url"""
    invitation_url_setting: dict = getattr(settings, "PROJECT_INVITATION_URL", {})

    site_domain = request.get_host()
    url = (
        site_domain in invitation_url_setting and invitation_url_setting[site_domain]
    ) or ("*" in invitation_url_setting and invitation_url_setting["*"])

    if not url:
        url = reverse("userprofile-list", request=request)

    return url


class ProjectInvitationEmail:
    """
    A class to send a project invitation email
    """

    def __init__(self, invitation: ProjectInvitation, url: str) -> None:
        super().__init__()

        self.invitation = invitation
        self.url = url

    def get_template_data(self) -> dict[str, str]:
        """Get context data for the templates"""
        deployment_name = getattr(settings, "DEPLOYMENT_NAME", "Ona")
        organization = self.invitation.project.organization.profile.name
        invited_by = None

        if self.invitation.invited_by:
            invited_by = self.invitation.invited_by.email

        data = {
            "subject": {"deployment_name": deployment_name},
            "body": {
                "deployment_name": deployment_name,
                "project_name": self.invitation.project.name,
                "invitation_url": self.url,
                "organization": organization,
                "invited_by": invited_by,
                "username": self.invitation.email,
            },
        }

        return data

    def get_email_data(self) -> dict[str, str]:
        """Get the email data to be sent"""
        template_data = self.get_template_data()
        custom_subject: str | None = getattr(
            settings, "PROJECT_INVITATION_SUBJECT", None
        )
        custom_message: str | None = getattr(
            settings, "PROJECT_INVITATION_MESSAGE", None
        )

        if custom_subject:
            subject = custom_subject.format(**template_data["subject"])

        else:
            subject_path = "projects/invitation_subject.txt"
            subject = render_to_string(subject_path, template_data["subject"])

        if custom_message:
            message = custom_message.format(**template_data["body"])

        else:
            message_path = "projects/invitation_message.html"
            message = render_to_string(
                message_path,
                template_data["body"],
            )

        return (
            subject,
            message,
        )

    def send(self) -> None:
        """Send project invitation email"""
        subject, message = self.get_email_data()
        send_mail(
            subject,
            strip_tags(message),
            settings.DEFAULT_FROM_EMAIL,
            (self.invitation.email,),
            html_message=message,
        )
