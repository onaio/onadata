# -*- coding: utf-8 -*-
"""
Management command used to generate platform statistics containing
information about the number of organizations, users, projects
& submissions
"""
import calendar
import csv
import os.path
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from multidb.pinning import use_master

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.logger.models import Instance, XForm
from onadata.libs.permissions import is_organization

User = get_user_model()


# pylint: disable=too-many-locals
def _write_stats_to_file(month: int, year: int, include_extra: bool, filename: str):
    with open(filename, "w", encoding="utf-8") as out_file:
        writer = csv.writer(out_file)
        headers = ["Username", "Project Name", "Form Title", "No. of submissions"]
        form_fields = [
            "id",
            "project__name",
            "project__organization__username",
            "title",
        ]
        if include_extra:
            headers += ["Is Organization", "Organization Created By", "User last login"]
            form_fields += ["project__organization__last_login"]

        writer.writerow(headers)
        _, last_day = calendar.monthrange(year, month)
        date_obj = timezone.make_aware(datetime(year, month, last_day), timezone.utc)

        forms = XForm.objects.filter(
            Q(deleted_at__isnull=True) | Q(deleted_at__gt=date_obj),
            date_created__lte=date_obj,
        ).values(*form_fields)
        with use_master:
            for form in forms:
                instance_count = Instance.objects.filter(
                    Q(deleted_at__isnull=True) | Q(deleted_at__gt=date_obj),
                    xform_id=form.get("id"),
                    date_created__lte=date_obj,
                ).count()
                row = [
                    form.get("project__organization__username"),
                    form.get("project__name"),
                    form.get("title"),
                    instance_count,
                ]
                if include_extra:
                    user = User.objects.get(
                        username=form.get("project__organization__username")
                    )
                    is_org = is_organization(user.profile)
                    if is_org:
                        created_by = OrganizationProfile.objects.get(
                            user=user
                        ).creator.username
                    else:
                        created_by = "N/A"
                    row += [
                        is_org,
                        created_by,
                        form.get("project__organization__last_login"),
                    ]
                writer.writerow(row)


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
                "Month to calculate system statistics for. Defaults to current month."
            ),
            default=None,
        )
        parser.add_argument(
            "--year",
            "-y",
            dest="year",
            help=("Year to calculate system statistics for. Defaults to current year"),
            default=None,
        )
        parser.add_argument(
            "--extra-info",
            "-e",
            action="store_true",
            dest="extra_info",
            default=False,
            help=(
                "Include extra information; When an Organization was created and "
                "user last login"
            ),
        )

    def handle(self, *args, **options):
        month = int(options.get("month") or datetime.now().month)
        year = int(options.get("year") or datetime.now().year)
        include_extra = bool(options.get("extra_info"))
        filename = f"platform_statistics_{month}_{year}.csv"
        _write_stats_to_file(month, year, include_extra, filename)
        if os.path.exists(filename):
            self.stdout.write(f"File '{filename}' successfully created.")
