"""
Management command used to generate platform statistics containing
information about the number of organizations, users, projects
& submissions
"""
import csv
import calendar
from datetime import datetime, date

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from django.db.models import Q

from multidb.pinning import use_master
from onadata.apps.logger.models import XForm, Instance


def _write_stats_to_file(month: int, year: int):
    out_file = open(f"/tmp/platform_statistics_{month}_{year}.csv", "w")  # nosec
    writer = csv.writer(out_file)
    headers = ["Username", "Project Name", "Form Title", "No. of submissions"]
    writer.writerow(headers)
    _, last_day = calendar.monthrange(year, month)
    date_obj = date(year, month, last_day)

    forms = XForm.objects.filter(
        Q(deleted_at__isnull=True) | Q(deleted_at__gt=date_obj),
        date_created__lte=date_obj,
    ).values("id", "project__name", "project__organization__username", "title")
    with use_master:
        for form in forms:
            instance_count = Instance.objects.filter(
                Q(deleted_at__isnull=True) | Q(deleted_at__gt=date_obj),
                xform_id=form.get("id"),
                date_created__lte=date_obj,
            ).count()
            writer.writerow(
                [
                    form.get("project__organization__username"),
                    form.get("project__name"),
                    form.get("title"),
                    instance_count,
                ]
            )


class Command(BaseCommand):
    """
    Management command used to generate platform statistics containing
    information about the number of organizations, users, projects
    & submissions
    """

    help = _("Generates system statistics for the entire platform")

    def add_arguments(self, parser):
        parser.add_argument(
            "--month",
            "-m",
            dest="month",
            help=(
                "Month to calculate system statistics for." "Defaults to current month."
            ),
            default=None,
        )
        parser.add_argument(
            "--year",
            "-y",
            dest="year",
            help=(
                "Year to calculate system statistics for." " Defaults to current year"
            ),
            default=None,
        )

    def handle(self, *args, **options):
        month = int(options.get("month", datetime.now().month))
        year = int(options.get("year", datetime.now().year))
        _write_stats_to_file(month, year)
