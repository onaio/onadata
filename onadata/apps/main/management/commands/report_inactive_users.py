# -*- coding: utf-8 -*-
"""
Write a CSV report for inactive-account deactivation lifecycle state.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.translation import gettext_lazy

from onadata.apps.main.models.user_deactivation import write_deactivation_report_csv


class Command(BaseCommand):
    """Write inactive-account lifecycle report rows as CSV."""

    help = gettext_lazy("Write inactive-account deactivation report rows as CSV.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--window-days",
            type=int,
            default=None,
            help=gettext_lazy(
                "Number of days before/after today to include in report cohorts."
            ),
        )
        parser.add_argument(
            "--csv",
            dest="csv_path",
            help=gettext_lazy("Path to write CSV output. Use '-' or omit for stdout."),
        )

    def handle(self, *args, **options):
        window_days = options["window_days"]
        csv_path = options["csv_path"]
        when = timezone.now()
        if window_days is not None and window_days <= 0:
            raise CommandError("--window-days must be greater than zero.")

        if csv_path and csv_path != "-":
            try:
                with open(csv_path, "w", encoding="utf-8", newline="") as csv_file:
                    row_count = write_deactivation_report_csv(
                        csv_file,
                        window_days=window_days,
                        when=when,
                    )
            except OSError as error:
                raise CommandError(
                    f"Could not write inactive-user report: {error}"
                ) from error

            if options["verbosity"] > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Wrote {row_count} inactive-user report rows to {csv_path}."
                    )
                )
            return

        write_deactivation_report_csv(
            self.stdout,
            window_days=window_days,
            when=when,
        )
