# -*- coding: utf-8 -*-
"""
Send warning emails for inactive-account deactivation.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext_lazy

from onadata.apps.api.tasks import send_account_deactivation_email
from onadata.apps.main.models.user_deactivation import (
    DEACTIVATION_ACTION_SEND_WARNING,
    dispatch_deactivation_warning,
    get_pending_deactivation_actions,
)


def enqueue_deactivation_warning_email(email, message_txt, subject):
    """
    Enqueue a deactivation warning email for asynchronous delivery.
    """
    send_account_deactivation_email.apply_async(args=(email, message_txt, subject))


class Command(BaseCommand):
    """Send inactive-account deactivation warning emails."""

    help = gettext_lazy("Send inactive-account deactivation warning emails.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=gettext_lazy("Report due warning emails without sending them."),
        )

    def handle(self, *args, **options):
        when = timezone.now()
        warning_actions = [
            action
            for action in get_pending_deactivation_actions(when=when)
            if action.action == DEACTIVATION_ACTION_SEND_WARNING
        ]

        if options["dry_run"]:
            if options["verbosity"] > 0:
                self.stdout.write(
                    f"Would queue {len(warning_actions)} inactive-account "
                    "warning emails."
                )
            return

        sent_count = 0
        skipped_count = 0
        for action in warning_actions:
            result = dispatch_deactivation_warning(
                action,
                enqueue_deactivation_warning_email,
                when=when,
            )
            if result.sent:
                sent_count += 1
            else:
                skipped_count += 1

        if options["verbosity"] > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Queued {sent_count} inactive-account warning emails; "
                    f"skipped {skipped_count}."
                )
            )
