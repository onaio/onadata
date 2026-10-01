"""Export deployment-wide account usage from retained submissions."""

import csv
import os
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from io import TextIOWrapper
from pathlib import PurePosixPath
from tempfile import TemporaryFile
from threading import Event, Thread
from time import monotonic
from typing import NamedTuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, DatabaseError, connections
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
PROGRESS_INTERVAL = 30
STREAM_CHUNK_SIZE = 10000
REPORT_FIELDS = (
    "account_id",
    "username",
    "account_type",
    "is_active",
    "total_admin_users",
    "total_data_collectors",
    "active_data_collectors",
    "submissions_last_12_months",
    "activity_year",
    "report_timestamp",
    "rolling_window_start",
)


class Report(NamedTuple):
    """How one report run is bounded, routed and paged."""

    database: str
    report_timestamp: datetime
    year_start: datetime
    activity_end: datetime
    rolling_start: datetime
    batch_size: int
    resume_from: int | None


class Command(BaseCommand):
    """Write one CSV row per existing personal or organization account."""

    help = "Export account administrators, data collectors and submission usage as CSV."
    verbosity = 1

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            help="Activity calendar year (default: the report timestamp's year).",
        )
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            choices=tuple(connections),
            help=(
                "Database alias for all report queries (default: default). "
                "Bypasses routers."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=BATCH_SIZE,
            help=(
                f"Accounts aggregated per query (default: {BATCH_SIZE}). Lower it "
                "when one batch holds an account large enough to change the plan."
            ),
        )
        parser.add_argument(
            "--resume-from",
            type=int,
            metavar="ACCOUNT_ID",
            help=(
                "Skip accounts up to and including ACCOUNT_ID, as reported by an "
                "interrupted run. Pair with --no-header and --csv, then "
                "concatenate; --storage uploads only a whole report."
            ),
        )
        parser.add_argument(
            "--no-header",
            action="store_true",
            help="Omit the header row, for appending to an earlier run's output.",
        )
        parser.add_argument(
            "--statement-timeout",
            type=int,
            metavar="MS",
            help=(
                "Set statement_timeout for this run's queries, in milliseconds; "
                "0 disables it. Without this the server default applies, which "
                "can be shorter than a full-history aggregate takes."
            ),
        )
        parser.add_argument(
            "--work-mem",
            type=int,
            metavar="MB",
            help=(
                "Set work_mem for this run's queries, in megabytes. Raising it "
                "keeps the per-account grouping in memory instead of temp files."
            ),
        )
        parser.add_argument(
            "--tmp-dir",
            metavar="DIR",
            help=(
                "Directory for the staged CSV when uploading to storage "
                "(default: FILE_UPLOAD_TEMP_DIR). Point it at real disk where "
                "the system temporary directory is memory backed."
            ),
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
        self.verbosity = options["verbosity"]
        report = self._plan(options)
        self._configure_session(report.database, options)
        header = not options["no_header"]
        rows = self._rows(report)

        self._message(f"Generating account usage report using '{report.database}'.")
        try:
            if options["storage"] is not None:
                self._save_to_storage(
                    options["storage"], rows, options["tmp_dir"], header
                )
            elif options["csv"] and options["csv"] != "-":
                self._write_file(options["csv"], rows, header)
            else:
                self._write_csv(self.stdout, rows, header)
        except OSError as error:
            raise CommandError(f"Unable to write report: {error}") from error
        self._message("Report complete.")

    @staticmethod
    def _plan(options):
        """Validate the request and resolve the boundaries every query shares.

        Everything rejectable is rejected here, before any output is opened or
        truncated and before the first query runs.
        """
        database = options["database"]
        if options["storage"] is not None and options["csv"] is not None:
            raise CommandError("--storage and --csv cannot be used together.")
        if database not in connections:
            raise CommandError(f"Unknown database alias: {database}")
        for name, minimum in (
            ("batch_size", 1),
            ("resume_from", 0),
            ("statement_timeout", 0),
            ("work_mem", 1),
        ):
            value = options[name]
            if value is not None and value < minimum:
                flag = name.replace("_", "-")
                raise CommandError(f"--{flag} must be at least {minimum}.")

        report_timestamp = timezone.now()
        deployment_timezone = (
            timezone.get_default_timezone() if settings.USE_TZ else None
        )
        if deployment_timezone is not None:
            report_timestamp = report_timestamp.astimezone(deployment_timezone)
        year = report_timestamp.year if options["year"] is None else options["year"]
        if not 1 <= year <= 9998:
            raise CommandError("--year must be between 1 and 9998.")

        year_start = datetime(year, 1, 1)
        year_end = datetime(year + 1, 1, 1)
        if deployment_timezone is not None:
            year_start = timezone.make_aware(year_start, deployment_timezone)
            year_end = timezone.make_aware(year_end, deployment_timezone)

        return Report(
            database=database,
            report_timestamp=report_timestamp,
            year_start=year_start,
            activity_end=min(year_end, report_timestamp),
            rolling_start=report_timestamp - relativedelta(months=12),
            batch_size=options["batch_size"],
            resume_from=options["resume_from"],
        )

    def _configure_session(self, database, options):
        """Apply the requested Postgres limits to this run's connection.

        ``set_config`` takes bound parameters where ``SET`` does not. Nothing
        outside this command shares the connection, so nothing inherits them.
        """
        connection = connections[database]
        if connection.vendor != "postgresql":
            return
        chosen = [
            (name, f"{value}{unit}")
            for name, value, unit in (
                ("statement_timeout", options["statement_timeout"], "ms"),
                ("work_mem", options["work_mem"], "MB"),
            )
            if value is not None
        ]
        if not chosen:
            return
        with connection.cursor() as cursor:
            for name, value in chosen:
                cursor.execute("SELECT set_config(%s, %s, false)", [name, value])
        limits = ", ".join(f"{name}={value}" for name, value in chosen)
        self._message(f"Session limits for '{database}': {limits}.")

    def _message(self, message):
        if self.verbosity > 0:
            self.stderr.write(message)
            self.stderr.flush()

    def _announce(self, processed, remaining, started, announced):
        """Report progress against the work left, at most once per interval."""
        if self.verbosity < 2 and monotonic() - announced < PROGRESS_INTERVAL:
            return announced
        self._message(f"Processed {self._summary(processed, remaining, started)}.")
        return monotonic()

    def _summary(self, processed, remaining, started):
        """Describe how far the run has got and roughly what is left.

        The estimate assumes accounts cost the same to aggregate, which one
        account holding most of the submissions breaks. Read it as an order of
        magnitude, not a deadline.
        """
        elapsed = monotonic() - started
        share = processed / remaining if remaining else 0
        if not share:
            return f"{processed} accounts in {self._duration(elapsed)}"
        left = max(elapsed / share - elapsed, 0)
        return (
            f"{processed} of {remaining} accounts ({share:.1%}) "
            f"in {self._duration(elapsed)}, ~{self._duration(left)} left"
        )

    @staticmethod
    def _duration(seconds):
        """Render a duration for progress lines."""
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h{minutes:02d}m"
        if minutes:
            return f"{minutes}m{seconds:02d}s"
        return f"{seconds}s"

    @contextmanager
    def _progress(self, stage, level=1):
        """Report a waiting stage without querying the database from another thread.

        ``level`` is the verbosity the start and finish lines need. The
        heartbeat runs regardless, so a stage that is actually slow still
        announces itself without every quick one doing the same.
        """
        if self.verbosity == 0:
            yield
            return

        started = monotonic()
        stopped = Event()
        detailed = self.verbosity >= level

        def heartbeat():
            while not stopped.wait(PROGRESS_INTERVAL):
                self._message(
                    f"{stage}: still waiting ({monotonic() - started:.0f}s elapsed)."
                )

        if detailed:
            self._message(f"{stage}...")
        worker = Thread(target=heartbeat, name="account-usage-progress", daemon=True)
        worker.start()
        try:
            yield
        finally:
            stopped.set()
            worker.join()
        if detailed:
            self._message(f"{stage}: done ({monotonic() - started:.1f}s).")

    @contextmanager
    def _stage(self, stage, last_pk):
        """Run one report query, turning a database failure into a resumable error."""
        with self._progress(stage, level=2):
            try:
                yield
            except DatabaseError as error:
                resume = (
                    f"Resume with --resume-from {last_pk}."
                    if last_pk is not None
                    else "No accounts completed; re-run the report."
                )
                raise CommandError(f"{stage} failed: {error} {resume}") from error

    @staticmethod
    def _write_csv(output, rows, header=True):
        writer = csv.writer(output, lineterminator="\n")
        if header:
            writer.writerow(REPORT_FIELDS)
        for row in rows:
            writer.writerow([sanitize_for_export(value) for value in row])

    def _write_file(self, path, rows, header):
        """Write beside the target and rename, so an interrupted run leaves a
        partial file under its own name rather than a truncated report."""
        partial = f"{path}.part"
        with open(partial, "w", encoding="utf-8", newline="") as output:
            self._write_csv(output, rows, header)
        os.replace(partial, path)

    def _save_to_storage(self, path, rows, tmp_dir, header):
        # Stage outside memory so large reports don't need to fit in it. Upload
        # bytes for both S3 and Azure, after the complete UTF-8 CSV is flushed.
        staging = tmp_dir or settings.FILE_UPLOAD_TEMP_DIR
        with (
            TemporaryFile(dir=staging) as report,
            TextIOWrapper(report, encoding="utf-8", newline="") as output,
        ):
            self._write_csv(output, rows, header)
            output.flush()
            report.seek(0)
            try:
                with self._progress(f"Uploading report to '{path}'"):
                    saved_path = default_storage.save(path, File(report, name=path))
            except Exception as error:  # pylint: disable=broad-exception-caught
                raise CommandError(
                    f"Unable to save report to storage: {error}"
                ) from error

        try:
            with self._progress("Generating download URL"):
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

    @staticmethod
    def _identified_submitter(database):
        """Match submissions from a named submitter without joining the user table.

        Comparing ``user__username`` inside the aggregates joined auth_user to
        every submission scanned, and ``iexact`` rules out any index on it.
        Usernames are unique, so the resolved ids say the same thing.
        """
        anonymous = list(
            get_user_model()
            .objects.using(database)
            .filter(username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME)
            .values_list("pk", flat=True)
        )
        identified = Q(user_id__isnull=False)
        if anonymous:
            identified &= ~Q(user_id__in=anonymous)
        return identified

    @staticmethod
    def _owner_counts(report, account_ids):
        """Count each organization's current owners, excluding the account itself.

        Rebuilding the name rather than matching its suffix costs a join to
        auth_user but lets the equality seek the unique index on auth_group
        .name, which a trailing wildcard could not.
        """
        return (
            Team.objects.using(report.database)
            .filter(
                organization_id__in=account_ids,
                name=Concat(
                    F("organization__username"),
                    Value(f"#{Team.OWNER_TEAM_NAME}"),
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

    @staticmethod
    def _count_submitters(report, account_ids, identified, window):
        """Count distinct submitters per account within ``window``.

        ``window`` is a (start, end) pair; ``start`` is None for all of
        retained history. Streaming the distinct pairs and counting them here
        leaves the server a plain GROUP BY: Postgres will not parallelise an
        aggregate with DISTINCT, which COUNT(DISTINCT user_id) would be.
        """
        start, end = window
        submissions = Instance.objects.using(report.database).filter(
            identified,
            xform__project__organization_id__in=account_ids,
            date_created__lt=end,
        )
        if start is not None:
            submissions = submissions.filter(date_created__gte=start)
        pairs = (
            submissions.order_by()
            .values_list("xform__project__organization_id", "user_id")
            .distinct()
            .iterator(chunk_size=STREAM_CHUNK_SIZE)
        )
        return Counter(account_id for account_id, _ in pairs)

    @staticmethod
    def _submission_counts(report, account_ids):
        """Count each account's submissions inside the rolling window."""
        return (
            Instance.objects.using(report.database)
            .filter(
                xform__project__organization_id__in=account_ids,
                date_created__gte=report.rolling_start,
                date_created__lt=report.report_timestamp,
            )
            .order_by()
            .values("xform__project__organization_id")
            .annotate(total=Count("pk"))
            .values_list("xform__project__organization_id", "total")
        )

    # pylint: disable=too-many-locals
    def _rows(self, report):
        base = (
            get_user_model()
            .objects.using(report.database)
            .exclude(username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME)
        )
        if report.resume_from is not None:
            base = base.filter(pk__gt=report.resume_from)
        accounts = base.order_by("pk").values(
            "pk", "username", "is_active", "profile__organizationprofile__pk"
        )
        processed = 0
        last_pk = report.resume_from
        started = monotonic()
        announced = started
        remaining = 0
        if self.verbosity > 0:
            # Counted off the unjoined queryset; the report's own select drags
            # in profile joins a count has no use for.
            with self._stage("Counting accounts to report", last_pk):
                remaining = base.count()
            self._message(f"{remaining} accounts to report.")
        with self._stage("Resolving anonymous submitters", last_pk):
            identified = self._identified_submitter(report.database)
        with self._stage("Reading account batch", last_pk):
            batch = list(accounts[: report.batch_size])
        while batch:
            account_ids = [account["pk"] for account in batch]
            label = f"accounts {processed + 1}-{processed + len(batch)}"
            # Keep these aggregations separate: joining teams to submissions would
            # multiply submission totals by the number of team members.
            with self._stage(f"Counting owners for {label}", last_pk):
                owner_counts = dict(self._owner_counts(report, account_ids))
            # Unfiltered managers include soft-deleted submissions/forms/projects.
            # Project ownership, rather than form ownership, attributes history.
            #
            # Three queries rather than one: only the submitter count needs all
            # of history, so the other two stay inside a date range the
            # (xform_id, date_created) index can walk.
            with self._stage(f"Counting submitters for {label}", last_pk):
                collectors = self._count_submitters(
                    report, account_ids, identified, (None, report.report_timestamp)
                )
            with self._stage(f"Counting active submitters for {label}", last_pk):
                active = self._count_submitters(
                    report,
                    account_ids,
                    identified,
                    (report.year_start, report.activity_end),
                )
            with self._stage(f"Counting submissions for {label}", last_pk):
                submissions = dict(self._submission_counts(report, account_ids))
            for account in batch:
                account_id = account["pk"]
                is_organization = (
                    account["profile__organizationprofile__pk"] is not None
                )
                yield (
                    account_id,
                    account["username"],
                    "organization" if is_organization else "personal",
                    account["is_active"],
                    owner_counts.get(account_id, 0) if is_organization else 1,
                    collectors[account_id],
                    active[account_id],
                    submissions.get(account_id, 0),
                    report.year_start.year,
                    report.report_timestamp.isoformat(),
                    report.rolling_start.isoformat(),
                )
            processed += len(batch)
            last_pk = batch[-1]["pk"]
            announced = self._announce(processed, remaining, started, announced)
            with self._stage("Reading account batch", last_pk):
                batch = list(accounts.filter(pk__gt=last_pk)[: report.batch_size])
        self._message(f"CSV generation complete: {processed} accounts.")
