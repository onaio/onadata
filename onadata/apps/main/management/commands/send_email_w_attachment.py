from typing import List

from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage


def send_email_w_attachment(
        attachment_path: str, recipients: List[str],
        subject: str, body: str, from_email: str):
    email = EmailMessage(
        subject,
        body,
        from_email,
        recipients)
    email.attach_file(attachment_path)
    email.send()


class Command(BaseCommand):
    """
    Management command used to send an email with an attachment
    """
    help = 'Send email with attachment'

    def add_arguments(self, parser):
        parser.add_argument(
            '-a', '--attachment', dest='attachment_path',
            type=str, help="Full path to attachment")
        parser.add_argument(
            '-r', '--recipients', dest='recipients',
            type=str, help="Comma-separated list of emails")
        parser.add_argument(
            '-s', '--subject', dest='subject',
            type=str, help="Email subject")
        parser.add_argument(
            '-b', '--body', dest='body',
            type=str, help="Email body")
        parser.add_argument(
            '-f', '--from', dest='from_email',
            type=str, default="noreply@ona.io", help="From email")

    def handle(self, *args, **options):
        send_email_w_attachment(
            options.get('attachment_path'),
            options.get('recipients').split(','),
            options.get('subject'),
            options.get('body'),
            options.get('from_email')
        )
