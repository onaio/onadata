# -*- coding: utf-8 -*-
"""
Delete expired, unconfirmed PendingEmailChange rows.
"""

from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy

from onadata.apps.main.models.pending_email_change import PendingEmailChange


class Command(BaseCommand):
    """Purge expired, unconfirmed email-change requests."""

    help = gettext_lazy("Delete PendingEmailChange rows whose OTP has expired.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=gettext_lazy(
                "Report how many rows would be deleted, without deleting."
            ),
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            due = PendingEmailChange.expired().count()
            if options["verbosity"] > 0:
                self.stdout.write(f"Would delete {due} expired email-change requests.")
            return

        deleted = PendingEmailChange.purge_expired()
        if options["verbosity"] > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {deleted} expired email-change requests.")
            )
