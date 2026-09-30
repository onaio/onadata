"""Export deployment-wide account usage from retained submissions."""

import csv
from contextlib import nullcontext
from datetime import datetime
from io import TextIOWrapper
from pathlib import PurePosixPath
from tempfile import TemporaryFile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, F, Q, Value
from django.db.models.functions import Concat
from django.utils import timezone
from django.utils.http import content_disposition_header

from dateutil.relativedelta import relativedelta

from onadata.apps.api.models import Team
from onadata.apps.logger.models import Instance
from onadata.libs.utils.common_tools import sanitize_for_export
from onadata.libs.utils.logger_tools import get_storages_media_download_url

BATCH_SIZE = 1000
REPORT_FIELDS = (
    "account_id",
    "username",
    "account_type",
    "total_admin_users",
    "total_data_collectors",
    "active_data_collectors",
    "submissions_last_12_months",
    "activity_year",
    "report_timestamp",
    "rolling_window_start",
)


class Command(BaseCommand):
    """Write one CSV row per existing personal or organization account."""

    help = "Export account administrators, data collectors and submission usage as CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=2026,
            help="Activity calendar year (default: 2026).",
        )
        output = parser.add_mutually_exclusive_group()
        output.add_argument(
            "--csv", help="Output file; omit or use '-' to write CSV to stdout."
        )
        output.add_argument(
            "--storage",
            metavar="PATH",
            help="Save CSV at PATH in default storage and print its download URL.",
        )

    def handle(self, *args, **options):
        year = options["year"]
        if not 1 <= year <= 9998:
            raise CommandError("--year must be between 1 and 9998.")
        if options["storage"] is not None and options["csv"] is not None:
            raise CommandError("--storage and --csv cannot be used together.")

        report_timestamp = timezone.now()
        year_start = datetime(year, 1, 1)
        year_end = datetime(year + 1, 1, 1)
        if settings.USE_TZ:
            deployment_timezone = timezone.get_default_timezone()
            report_timestamp = report_timestamp.astimezone(deployment_timezone)
            year_start = timezone.make_aware(year_start, deployment_timezone)
            year_end = timezone.make_aware(year_end, deployment_timezone)
        rolling_start = report_timestamp - relativedelta(months=12)
        rows = self._rows(year_start, year_end, report_timestamp, rolling_start)

        output_path = options["csv"]
        try:
            if options["storage"] is not None:
                self._save_to_storage(options["storage"], rows)
                return
            with (
                open(output_path, "w", encoding="utf-8", newline="")
                if output_path and output_path != "-"
                else nullcontext(self.stdout)
            ) as output:
                self._write_csv(output, rows)
        except OSError as error:
            raise CommandError(f"Unable to write report: {error}") from error

    @staticmethod
    def _write_csv(output, rows):
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(REPORT_FIELDS)
        for row in rows:
            writer.writerow([sanitize_for_export(value) for value in row])

    def _save_to_storage(self, path, rows):
        # Stage on disk so large reports don't need to fit in memory. Upload bytes
        # for both S3 and Azure, after the complete UTF-8 CSV has been flushed.
        with TemporaryFile() as report, TextIOWrapper(
            report, encoding="utf-8", newline=""
        ) as output:
            self._write_csv(output, rows)
            output.flush()
            report.seek(0)
            try:
                saved_path = default_storage.save(path, File(report, name=path))
            except Exception as error:  # pylint: disable=broad-exception-caught
                raise CommandError(
                    f"Unable to save report to storage: {error}"
                ) from error

        try:
            url = get_storages_media_download_url(
                saved_path,
                content_disposition_header(True, PurePosixPath(saved_path).name),
                "text/csv",
            ) or default_storage.url(saved_path)
        except Exception as error:  # pylint: disable=broad-exception-caught
            raise CommandError(
                f"Report saved to '{saved_path}', "
                f"but unable to generate its URL: {error}"
            ) from error
        self.stdout.write(url)

    def _rows(self, year_start, year_end, report_timestamp, rolling_start):
        accounts = (
            get_user_model()
            .objects.exclude(username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME)
            .order_by("pk")
            .values("pk", "username", "profile__organizationprofile__pk")
        )
        identified = Q(user__isnull=False) & ~Q(
            user__username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
        )
        batch = list(accounts[:BATCH_SIZE])
        while batch:
            account_ids = [account["pk"] for account in batch]
            # Keep these aggregations separate: joining teams to submissions would
            # multiply submission totals by the number of team members.
            owner_counts = dict(
                Team.objects.filter(
                    organization_id__in=account_ids,
                    name=Concat(
                        F("organization__username"), Value(f"#{Team.OWNER_TEAM_NAME}")
                    ),
                )
                .order_by()
                .values("organization_id")
                .annotate(
                    total=Count(
                        "user",
                        filter=~Q(user__pk=F("organization_id")),
                        distinct=True,
                    )
                )
                .values_list("organization_id", "total")
            )
            # Unfiltered managers include soft-deleted submissions/forms/projects.
            # Project ownership, rather than form ownership, attributes history.
            usage = {
                row["xform__project__organization_id"]: row
                for row in Instance.objects.filter(
                    xform__project__organization_id__in=account_ids,
                    date_created__lt=report_timestamp,
                )
                .order_by()
                .values("xform__project__organization_id")
                .annotate(
                    collectors=Count("user_id", filter=identified, distinct=True),
                    active=Count(
                        "user_id",
                        filter=identified
                        & Q(date_created__gte=year_start, date_created__lt=year_end),
                        distinct=True,
                    ),
                    submissions=Count("pk", filter=Q(date_created__gte=rolling_start)),
                )
            }
            for account in batch:
                account_id = account["pk"]
                is_organization = (
                    account["profile__organizationprofile__pk"] is not None
                )
                counts = usage.get(account_id, {})
                yield (
                    account_id,
                    account["username"],
                    "organization" if is_organization else "personal",
                    owner_counts.get(account_id, 0) if is_organization else 1,
                    counts.get("collectors", 0),
                    counts.get("active", 0),
                    counts.get("submissions", 0),
                    year_start.year,
                    report_timestamp.isoformat(),
                    rolling_start.isoformat(),
                )
            batch = list(accounts.filter(pk__gt=batch[-1]["pk"])[:BATCH_SIZE])
