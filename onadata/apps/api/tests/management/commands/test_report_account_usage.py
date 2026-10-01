"""Behavioral tests for the deployment-wide account usage CSV."""

import csv
from contextlib import nullcontext
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from onadata.apps.api.management.commands import report_account_usage
from onadata.apps.api.models import OrganizationProfile, Team
from onadata.apps.logger.models import Instance, Project, SurveyType, XForm
from onadata.apps.logger.models.instance import InstanceHistory
from onadata.apps.main.models import UserProfile

User = get_user_model()
UTC = datetime_timezone.utc
REPORT_TIME = datetime(2026, 9, 30, 12, tzinfo=UTC)
RECENT = datetime(2026, 6, 1, tzinfo=UTC)
HISTORICAL = datetime(2024, 6, 1, tzinfo=UTC)


@override_settings(TIME_ZONE="UTC", USE_TZ=True)
class ReportAccountUsageTest(TestCase):
    """Reports count retained records without changing account state."""

    @classmethod
    def setUpTestData(cls):
        # Bulk fixtures avoid unrelated publishing, parsing and permission signals.
        cls.owner, cls.org, cls.collector, cls.inactive = User.objects.bulk_create(
            [
                User(username="owner"),
                User(username="organization", is_active=False),
                User(username="collector"),
                User(username="inactive", is_active=False),
            ]
        )
        UserProfile.objects.create(user=cls.owner)
        cls.organization = OrganizationProfile.objects.create(
            user=cls.org, creator=cls.owner, created_by=cls.owner
        )
        cls.project, cls.personal_project = Project.objects.bulk_create(
            [
                Project(
                    name="Organization", organization=cls.org, created_by=cls.owner
                ),
                Project(name="Personal", organization=cls.owner, created_by=cls.owner),
            ]
        )
        cls.form, cls.personal_form = XForm.objects.bulk_create(
            [
                XForm(project=cls.project, user=cls.org, id_string="organization"),
                XForm(
                    project=cls.personal_project, user=cls.owner, id_string="personal"
                ),
            ]
        )
        cls.survey_type = SurveyType.objects.create(slug="account-usage-test")

    def _submit(self, user, received=RECENT, form=None, **kwargs):
        return Instance.objects.bulk_create(
            [
                Instance(
                    user=user,
                    xform=form or self.form,
                    survey_type=self.survey_type,
                    date_created=received,
                    uuid=str(uuid4()),
                    **kwargs,
                )
            ]
        )[0]

    def _report(self, now=REPORT_TIME, **options):
        output = StringIO()
        options.setdefault("stderr", StringIO())
        with patch.object(
            report_account_usage.timezone, "now", return_value=now
        ) as clock:
            call_command("report_account_usage", stdout=output, **options)
        clock.assert_called_once_with()
        return {
            int(row["account_id"]): row
            for row in csv.DictReader(StringIO(output.getvalue()))
        }

    def _assert_metrics(self, row, admins=1, collectors=0, active=0, submissions=0):
        self.assertEqual(row["total_admin_users"], str(admins))
        self.assertEqual(row["total_data_collectors"], str(collectors))
        self.assertEqual(row["active_data_collectors"], str(active))
        self.assertEqual(row["submissions_last_12_months"], str(submissions))

    def test_all_accounts_including_inactive_profileless_and_empty(self):
        """User enumeration includes accounts with no profile or retained data."""
        profile_count = UserProfile.objects.count()
        team_count = Team.objects.count()
        rows = self._report()
        expected_ids = set(
            User.objects.exclude(
                username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
            ).values_list("pk", flat=True)
        )
        self.assertEqual(set(rows), expected_ids)
        self.assertEqual(list(rows), sorted(expected_ids))
        for account in (self.owner, self.collector, self.inactive):
            self._assert_metrics(rows[account.pk])
            self.assertEqual(rows[account.pk]["account_type"], "personal")
        self.assertEqual(rows[self.org.pk]["account_type"], "organization")
        self._assert_metrics(rows[self.org.pk])
        self.assertEqual(rows[self.owner.pk]["is_active"], "True")
        self.assertEqual(rows[self.collector.pk]["is_active"], "True")
        self.assertEqual(rows[self.inactive.pk]["is_active"], "False")
        self.assertEqual(rows[self.org.pk]["is_active"], "False")
        for row in rows.values():
            self.assertEqual(row["activity_year"], "2026")
            self.assertEqual(row["report_timestamp"], REPORT_TIME.isoformat())
            self.assertEqual(row["rolling_window_start"], "2025-09-30T12:00:00+00:00")
        self.assertEqual(UserProfile.objects.count(), profile_count)
        self.assertEqual(Team.objects.count(), team_count)

    def test_only_current_owners_count_without_activity_or_join_date_filters(self):
        """Former owners and the organization itself are excluded."""
        owners = Team.objects.get(organization=self.org, name="organization#Owners")
        self.owner.groups.remove(owners)
        owners.user_set.add(self.collector, self.inactive, self.org)
        User.objects.filter(pk=self.inactive.pk).update(
            date_joined=datetime(2027, 1, 1, tzinfo=UTC)
        )
        members = Team.objects.create(organization=self.org, name="Members")
        members.user_set.add(self.owner, self.collector)
        self._submit(self.collector)
        self._submit(self.owner)
        self._assert_metrics(
            self._report()[self.org.pk], admins=2, collectors=2, active=2, submissions=2
        )

    def test_missing_owners_team_stays_missing(self):
        """Reporting never repairs missing teams."""
        Team.objects.filter(organization=self.org).delete()
        self._assert_metrics(self._report()[self.org.pk], admins=0)
        self.assertFalse(Team.objects.filter(organization=self.org).exists())

    def test_collectors_deduplicated_across_forms_and_projects_per_account(self):
        """Admins and inactive submitters count; other accounts stay separate."""
        another_project = Project.objects.bulk_create(
            [Project(name="Second", organization=self.org, created_by=self.owner)]
        )[0]
        second_form, third_form = XForm.objects.bulk_create(
            [
                XForm(
                    project=self.project,
                    user=self.org,
                    id_string="second",
                    sms_id_string="second",
                ),
                XForm(
                    project=another_project,
                    user=self.org,
                    id_string="third",
                    sms_id_string="third",
                ),
            ]
        )
        for form in (self.form, self.form, second_form, third_form):
            self._submit(self.collector, form=form)
        self._submit(self.owner)
        self._submit(self.inactive, HISTORICAL)
        self._submit(self.collector, form=self.personal_form)
        self._submit(self.inactive, form=self.personal_form)
        rows = self._report()
        self._assert_metrics(rows[self.org.pk], collectors=3, active=2, submissions=5)
        self._assert_metrics(rows[self.owner.pk], collectors=2, active=2, submissions=2)

    @override_settings(TIME_ZONE="Africa/Nairobi")
    def test_calendar_year_uses_deployment_timezone_with_exclusive_end(self):
        """Calendar boundaries use TIME_ZONE, even if another zone is active."""
        start = datetime(2025, 12, 31, 21, tzinfo=UTC)
        end = datetime(2026, 12, 31, 21, tzinfo=UTC)
        for user, received in zip(
            (self.owner, self.collector, self.inactive, self.org),
            (
                start - timedelta(microseconds=1),
                start,
                end - timedelta(microseconds=1),
                end,
            ),
        ):
            self._submit(user, received)
        with timezone.override("Pacific/Honolulu"):
            rows = self._report(now=datetime(2027, 3, 1, tzinfo=UTC), year=2026)
        self._assert_metrics(rows[self.org.pk], collectors=4, active=2, submissions=2)
        self.assertEqual(
            rows[self.org.pk]["report_timestamp"], "2027-03-01T03:00:00+03:00"
        )

    def test_activity_and_submission_counts_stop_before_report_timestamp(self):
        """The timestamp is an exclusive upper bound, including for the current year."""
        self._submit(self.collector, REPORT_TIME - timedelta(microseconds=1))
        self._submit(self.inactive, REPORT_TIME)
        self._submit(self.owner, REPORT_TIME + timedelta(microseconds=1))
        self._assert_metrics(
            self._report()[self.org.pk], collectors=1, active=1, submissions=1
        )
        self._assert_metrics(
            self._report(year=2027)[self.org.pk], collectors=1, active=0, submissions=1
        )

    @override_settings(TIME_ZONE="America/New_York")
    def test_rolling_calendar_months_handle_leap_day_and_dst(self):
        """Twelve calendar months preserve local wall time and clamp February 29."""
        for now, expected_start in (
            (datetime(2024, 2, 29, 12, tzinfo=UTC), "2023-02-28T07:00:00-05:00"),
            (datetime(2026, 3, 8, 7, 30, tzinfo=UTC), "2025-03-08T03:30:00-05:00"),
        ):
            with self.subTest(now=now):
                start = datetime.fromisoformat(expected_start)
                self._submit(self.collector, start - timedelta(microseconds=1))
                self._submit(self.collector, start)
                self._submit(self.collector, now - timedelta(microseconds=1))
                self._submit(self.collector, now)
                row = self._report(now=now, year=now.year)[self.org.pk]
                self.assertEqual(row["rolling_window_start"], expected_start)
                self._assert_metrics(row, collectors=1, active=1, submissions=2)

    def test_soft_deleted_records_and_current_project_ownership(self):
        """Retained data follow project ownership even if form.user differs."""
        self._submit(self.collector, deleted_at=REPORT_TIME)
        self._submit(self.inactive)
        XForm.objects.filter(pk=self.form.pk).update(deleted_at=REPORT_TIME)
        Project.objects.filter(pk=self.project.pk).update(
            deleted_at=REPORT_TIME, organization=self.owner
        )
        rows = self._report()
        self._assert_metrics(rows[self.org.pk])
        self._assert_metrics(rows[self.owner.pk], collectors=2, active=2, submissions=2)

    @override_settings(ANONYMOUS_DEFAULT_USERNAME="system-guest")
    def test_anonymous_submissions_count_but_cannot_identify_collectors(self):
        """Both NULL submitters and the configured system account are anonymous."""
        anonymous = User.objects.bulk_create([User(username="System-Guest")])[0]
        self._submit(None)
        self._submit(anonymous)
        self._submit(self.collector)
        rows = self._report()
        self.assertNotIn(anonymous.pk, rows)
        self._assert_metrics(rows[self.org.pk], collectors=1, active=1, submissions=3)

    def test_edits_do_not_change_receipt_date_or_count_as_submissions(self):
        """History and editors do not affect the original submission's metrics."""
        for received in (HISTORICAL, RECENT):
            submission = self._submit(
                self.collector,
                received,
                date_modified=RECENT,
                last_edited=RECENT,
                last_edited_by=self.inactive,
            )
            InstanceHistory.objects.bulk_create(
                [
                    InstanceHistory(xform_instance=submission, user=self.inactive)
                    for _ in range(2)
                ]
            )
        self._assert_metrics(
            self._report()[self.org.pk], collectors=1, active=1, submissions=1
        )

    def test_stdout_file_output_and_csv_sanitization(self):
        """Both destinations contain only the same valid, sanitized UTF-8 CSV."""
        formula, quoted = User.objects.bulk_create(
            [User(username="=formula"), User(username='élise, "quoted"')]
        )
        rows = self._report()
        self.assertEqual(rows[formula.pk]["username"], "'=formula")
        self.assertEqual(rows[quoted.pk]["username"], quoted.username)
        self.assertEqual(rows, self._report(csv="-"))
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "report.csv"
            self.assertEqual(self._report(csv=str(output_path)), {})
            with output_path.open(encoding="utf-8", newline="") as report:
                reader = csv.DictReader(report)
                self.assertEqual(
                    reader.fieldnames,
                    [
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
                    ],
                )
                self.assertEqual({int(row["account_id"]): row for row in reader}, rows)

    def test_invalid_year_and_file_errors_raise_command_error(self):
        """Bad years fail before opening files; file failures have command errors."""
        for year in ("invalid", "0", "-1", "9999", "10000"):
            with self.subTest(year=year), patch("builtins.open") as open_file:
                with self.assertRaises(CommandError):
                    call_command(
                        "report_account_usage",
                        "--year",
                        year,
                        csv="report.csv",
                        stdout=StringIO(),
                    )
                open_file.assert_not_called()
        with TemporaryDirectory() as directory:
            # Nested so the staged .part file is removed with the directory.
            nested = Path(directory) / "nested"
            nested.mkdir()
            with self.assertRaisesMessage(CommandError, "Unable to write report"):
                self._report(csv=str(nested))
            with patch("builtins.open", side_effect=PermissionError("denied")):
                with self.assertRaisesMessage(CommandError, "Unable to write report"):
                    self._report(csv=str(Path(directory) / "report.csv"))
        with (
            patch.object(
                report_account_usage.csv, "writer", side_effect=OSError("disk full")
            ),
            self.assertRaisesMessage(CommandError, "Unable to write report"),
        ):
            self._report()

    @override_settings(
        STORAGES={
            "default": {
                "BACKEND": "django.core.files.storage.InMemoryStorage",
                "OPTIONS": {"base_url": "https://storage.example.test/media/"},
            }
        }
    )
    def test_storage_upload_matches_csv_and_links_to_actual_saved_name(self):
        """Stored CSV retains encoding/sanitization and uses the backend's filename."""
        User.objects.bulk_create([User(username="=formula"), User(username="élise")])
        self._submit(self.collector)
        expected = self._report()
        storage = storages["default"]
        requested_path = "reports/account_usage.csv"
        storage.save(requested_path, ContentFile(b"previous report"))
        output = StringIO()
        progress = StringIO()
        with (
            patch.object(
                report_account_usage.timezone, "now", return_value=REPORT_TIME
            ),
            patch.object(storage, "url", wraps=storage.url) as storage_url,
        ):
            call_command(
                "report_account_usage",
                storage=requested_path,
                stdout=output,
                stderr=progress,
            )
        saved_path = storage_url.call_args.args[0]
        self.assertNotEqual(saved_path, requested_path)
        self.assertEqual(output.getvalue(), storage.url(saved_path) + "\n")
        self.assertIn(f"Uploading report to '{requested_path}'...", progress.getvalue())
        self.assertIn("Generating download URL...", progress.getvalue())
        self.assertTrue(progress.getvalue().endswith("Report complete.\n"))
        with storage.open(saved_path, "rb") as report:
            reader = csv.DictReader(StringIO(report.read().decode("utf-8")))
            self.assertEqual({int(row["account_id"]): row for row in reader}, expected)
        with storage.open(requested_path, "rb") as previous:
            self.assertEqual(previous.read(), b"previous report")

    def test_s3_and_azure_upload_bytes_and_request_download_links(self):
        """Cloud backends receive a binary CSV and a one-hour attachment URL request."""
        requested_path = "reports/account_usage.csv"
        saved_path = "reports/renamed.csv"
        download_url = (
            "https://storage.example.test/reports/renamed.csv?signature=example"
        )

        def save_report(name, content):
            self.assertEqual(name, requested_path)
            self.assertEqual(content.name, requested_path)
            data = content.read()
            self.assertIsInstance(data, bytes)
            self.assertTrue(data.startswith(b"account_id,username,account_type,"))
            return saved_path

        for backend, options, parameters in (
            (
                "storages.backends.s3.S3Storage",
                {"bucket_name": "reports"},
                {
                    "ResponseContentDisposition": 'attachment; filename="renamed.csv"',
                    "ResponseContentType": "text/csv",
                },
            ),
            (
                "storages.backends.azure_storage.AzureStorage",
                {"account_name": "reports", "azure_container": "reports"},
                {
                    "content_disposition": 'attachment; filename="renamed.csv"',
                    "content_type": "text/csv",
                },
            ),
        ):
            with (
                self.subTest(backend=backend),
                override_settings(
                    STORAGES={"default": {"BACKEND": backend, "OPTIONS": options}}
                ),
            ):
                storage = storages["default"]
                output = StringIO()
                with patch.object(storage, "save", side_effect=save_report) as save:
                    with patch.object(storage, "url", return_value=download_url) as url:
                        call_command(
                            "report_account_usage",
                            storage=requested_path,
                            stdout=output,
                            stderr=StringIO(),
                        )
                save.assert_called_once()
                url.assert_called_once_with(
                    saved_path, parameters=parameters, expire=3600
                )
                self.assertEqual(output.getvalue(), download_url + "\n")

    @override_settings(
        STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}}
    )
    def test_storage_failures_raise_command_errors(self):
        """Cloud-style errors are reported; URL errors preserve the saved path."""
        storage = storages["default"]
        output = StringIO()
        progress = StringIO()
        with patch.object(storage, "save", side_effect=RuntimeError("upload failed")):
            with self.assertRaisesMessage(
                CommandError, "Unable to save report to storage"
            ):
                call_command(
                    "report_account_usage",
                    storage="report.csv",
                    stdout=output,
                    stderr=progress,
                )
        self.assertEqual(output.getvalue(), "")
        with patch.object(storage, "url", side_effect=NotImplementedError("no URL")):
            with self.assertRaisesMessage(CommandError, "Report saved to 'report.csv'"):
                call_command(
                    "report_account_usage",
                    storage="report.csv",
                    stdout=output,
                    stderr=progress,
                )
        self.assertTrue(storage.exists("report.csv"))
        self.assertEqual(output.getvalue(), "")
        self.assertNotIn("Report complete.", progress.getvalue())

    def test_storage_and_local_output_are_mutually_exclusive(self):
        """Invalid output combinations fail before file writes or account queries."""
        with (
            self.assertNumQueries(0),
            patch.object(report_account_usage, "default_storage") as storage,
        ):
            with self.assertRaises(CommandError):
                call_command(
                    "report_account_usage", "--csv", "-", "--storage", "report.csv"
                )
            with self.assertRaises(CommandError):
                call_command(
                    "report_account_usage", csv="local.csv", storage="report.csv"
                )
            storage.save.assert_not_called()

    def test_query_growth_is_per_batch_and_report_is_read_only(self):
        """Adding accounts within a batch adds no queries; crossing adds one batch."""
        account_count = User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
        ).count()
        # Per batch: owners, submitters, active submitters, submissions and the
        # next batch of accounts. Once overall: the remaining-account count,
        # the anonymous account lookup and the first batch of accounts.
        per_batch = 5
        overhead = 3
        batch_size = account_count + 6
        with CaptureQueriesContext(connection) as first:
            expected_rows = self._report(batch_size=batch_size)
        self.assertEqual(len(first), overhead + per_batch)
        User.objects.bulk_create(
            [User(username=f"extra-{index}") for index in range(5)]
        )
        with CaptureQueriesContext(connection) as second:
            rows = self._report(batch_size=batch_size)
        self.assertEqual(len(rows), len(expected_rows) + 5)
        self.assertEqual(len(first), len(second))
        _, last_account = User.objects.bulk_create(
            [User(username="next-batch-1"), User(username="next-batch-2")]
        )
        # Move existing data into the final batch to verify its aggregates.
        Project.objects.filter(pk=self.project.pk).update(organization=last_account)
        self._submit(self.collector)
        with CaptureQueriesContext(connection) as third:
            rows = self._report(batch_size=batch_size)
        self.assertEqual(len(rows), len(expected_rows) + 7)
        self._assert_metrics(
            rows[last_account.pk], collectors=1, active=1, submissions=1
        )
        self.assertEqual(len(third) - len(second), per_batch)
        self.assertEqual(len(third), overhead + 2 * per_batch)
        for query in third:
            self.assertNotRegex(
                query["sql"], r"(?i)\b(INSERT|UPDATE|DELETE|TRUNCATE)\b"
            )

    @override_settings(DATABASE_ROUTERS=["multidb.MasterSlaveRouter"])
    def test_report_queries_bypass_replica_routing(self):
        """All account, owner and submission queries stay on the selected database."""
        self._submit(self.collector)
        for options in ({}, {"database": "default"}):
            with (
                self.subTest(options=options),
                patch(
                    "multidb.get_slave", return_value="unavailable-replica"
                ) as get_replica,
            ):
                rows = self._report(batch_size=2, **options)
            get_replica.assert_not_called()
            self._assert_metrics(
                rows[self.org.pk], collectors=1, active=1, submissions=1
            )

    def test_unknown_database_fails_before_opening_output(self):
        """Reject an invalid database alias without truncating an output file."""
        with self.assertNumQueries(0), patch("builtins.open") as open_file:
            with self.assertRaisesMessage(CommandError, "Unknown database alias"):
                call_command(
                    "report_account_usage", database="missing", csv="report.csv"
                )
            open_file.assert_not_called()

    def test_stage_detail_needs_higher_verbosity_than_run_boundaries(self):
        """Per-batch stages are -v2 detail; the default keeps the run's outline."""
        detailed = StringIO()
        rows = self._report(stderr=detailed, batch_size=2, verbosity=2)
        messages = detailed.getvalue()
        self.assertIn("Generating account usage report using 'default'.", messages)
        self.assertIn("Counting owners for accounts 1-2...", messages)
        self.assertIn("Counting submitters for accounts 1-2...", messages)
        self.assertIn("Counting active submitters for accounts 1-2...", messages)
        self.assertIn("Counting submissions for accounts 1-2...", messages)
        self.assertIn(f"{len(rows)} accounts to report.", messages)
        self.assertIn(f"Processed 2 of {len(rows)} accounts (50.0%)", messages)
        self.assertIn(f"CSV generation complete: {len(rows)} accounts.", messages)
        self.assertTrue(messages.endswith("Report complete.\n"))

        default = StringIO()
        self.assertEqual(self._report(stderr=default, batch_size=2), rows)
        outline = default.getvalue()
        self.assertNotIn("Counting owners", outline)
        self.assertNotIn("Processed 2 of", outline)
        self.assertIn(f"{len(rows)} accounts to report.", outline)
        self.assertIn("Generating account usage report using 'default'.", outline)
        self.assertIn(f"CSV generation complete: {len(rows)} accounts.", outline)
        self.assertTrue(outline.endswith("Report complete.\n"))

    def test_quiet_verbosity_disables_progress_and_heartbeat_threads(self):
        """Quiet mode retains the report without starting progress workers."""
        progress = StringIO()
        with patch.object(report_account_usage, "Thread") as worker:
            rows = self._report(verbosity=0, stderr=progress)
        self.assertIn(self.org.pk, rows)
        self.assertEqual(progress.getvalue(), "")
        worker.assert_not_called()

    def test_heartbeat_during_wait_stops_on_success_and_error(self):
        """A waiting operation emits elapsed time and always joins its worker."""
        workers = []

        def new_worker(**kwargs):
            worker = Thread(**kwargs)
            workers.append(worker)
            return worker

        for fails in (False, True):
            with self.subTest(fails=fails):
                progress = StringIO()
                heartbeat_seen = Event()
                original_write = progress.write

                def write(message):
                    result = original_write(message)
                    if "still waiting" in message:
                        heartbeat_seen.set()
                    return result

                command = report_account_usage.Command(stderr=progress)
                command.verbosity = 1
                with (
                    patch.object(report_account_usage, "PROGRESS_INTERVAL", 0.01),
                    patch.object(
                        report_account_usage, "Thread", side_effect=new_worker
                    ),
                    patch.object(progress, "write", side_effect=write),
                    (
                        self.assertRaisesMessage(RuntimeError, "query failed")
                        if fails
                        else nullcontext()
                    ),
                    command._progress("Aggregating submissions"),
                ):
                    self.assertTrue(heartbeat_seen.wait(timeout=2))
                    if fails:
                        raise RuntimeError("query failed")
                self.assertIn("still waiting", progress.getvalue())
                self.assertIn("elapsed", progress.getvalue())
                self.assertEqual("done" in progress.getvalue(), not fails)
                self.assertFalse(workers[-1].is_alive())

    @override_settings(USE_TZ=False)
    def test_timezone_support_can_be_disabled(self):
        """Naive deployments still report local calendar boundaries."""
        row = self._report(now=REPORT_TIME.replace(tzinfo=None))[self.owner.pk]
        self.assertEqual(row["report_timestamp"], "2026-09-30T12:00:00")
        self.assertEqual(row["rolling_window_start"], "2025-09-30T12:00:00")

    def test_activity_year_defaults_to_the_report_timestamp_year(self):
        """Without --year the report describes the year it was generated in."""
        rows = self._report(now=datetime(2031, 5, 4, tzinfo=UTC))
        self.assertEqual({row["activity_year"] for row in rows.values()}, {"2031"})

    def test_tuning_options_are_validated_before_any_query(self):
        """Out-of-range paging and session limits fail without touching the data."""
        for option, value in (
            ("batch_size", 0),
            ("resume_from", -1),
            ("statement_timeout", -1),
            ("work_mem", 0),
        ):
            with self.subTest(option=option), self.assertNumQueries(0):
                with self.assertRaisesMessage(CommandError, "must be at least"):
                    call_command(
                        "report_account_usage", stdout=StringIO(), **{option: value}
                    )

    def test_resume_from_continues_after_the_last_reported_account(self):
        """Resuming skips reported accounts and can leave the header off."""
        complete = sorted(self._report())
        output = StringIO()
        with patch.object(
            report_account_usage.timezone, "now", return_value=REPORT_TIME
        ):
            call_command(
                "report_account_usage",
                resume_from=complete[0],
                no_header=True,
                stdout=output,
                stderr=StringIO(),
            )
        lines = output.getvalue().splitlines()
        self.assertNotIn("account_id", lines[0])
        self.assertEqual([int(line.split(",")[0]) for line in lines], complete[1:])

    def test_interrupted_aggregates_name_the_account_to_resume_from(self):
        """A database failure says where to restart, or that nothing finished."""
        accounts = sorted(
            User.objects.exclude(
                username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
            ).values_list("pk", flat=True)
        )
        original = report_account_usage.Command._submission_counts
        batches = []

        def fail_after(limit):
            def aggregate(report, account_ids):
                batches.append(account_ids)
                if len(batches) > limit:
                    raise DatabaseError("canceling statement due to statement timeout")
                return original(report, account_ids)

            return aggregate

        for limit, expected in (
            (0, "No accounts completed"),
            (1, f"Resume with --resume-from {accounts[0]}"),
        ):
            with self.subTest(limit=limit):
                batches.clear()
                with (
                    patch.object(
                        report_account_usage.Command,
                        "_submission_counts",
                        staticmethod(fail_after(limit)),
                    ),
                    self.assertRaisesMessage(CommandError, expected),
                ):
                    call_command(
                        "report_account_usage",
                        batch_size=1,
                        stdout=StringIO(),
                        stderr=StringIO(),
                    )

    def test_a_failed_run_leaves_a_partial_file_not_a_short_report(self):
        """The requested name appears only once a whole report is written."""

        def fail(report, account_ids):
            raise DatabaseError("canceling statement due to statement timeout")

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "report.csv"
            partial = Path(f"{output_path}.part")
            with (
                patch.object(
                    report_account_usage.timezone, "now", return_value=REPORT_TIME
                ),
                patch.object(
                    report_account_usage.Command,
                    "_submission_counts",
                    staticmethod(fail),
                ),
                self.assertRaises(CommandError),
            ):
                call_command(
                    "report_account_usage",
                    csv=str(output_path),
                    stdout=StringIO(),
                    stderr=StringIO(),
                )
            self.assertFalse(output_path.exists())
            self.assertEqual(
                partial.read_text(encoding="utf-8").splitlines(),
                [",".join(report_account_usage.REPORT_FIELDS)],
            )
            self.assertEqual(self._report(csv=str(output_path)), {})
            self.assertTrue(output_path.exists())
            self.assertFalse(partial.exists())

    def test_progress_counts_only_the_accounts_still_to_report(self):
        """Resuming measures progress against what is left, not the whole table."""
        accounts = sorted(self._report())
        progress = StringIO()
        with patch.object(
            report_account_usage.timezone, "now", return_value=REPORT_TIME
        ):
            call_command(
                "report_account_usage",
                resume_from=accounts[0],
                batch_size=1,
                verbosity=2,
                stdout=StringIO(),
                stderr=progress,
            )
        messages = progress.getvalue()
        left = len(accounts) - 1
        self.assertIn(f"{left} accounts to report.", messages)
        self.assertIn(f"Processed 1 of {left} accounts", messages)
        self.assertIn(f"CSV generation complete: {left} accounts.", messages)

    def test_session_limits_are_applied_as_bound_values(self):
        """Both limits reach the connection the report queries run on."""
        with CaptureQueriesContext(connection) as queries:
            self._report(statement_timeout=0, work_mem=64)
        applied = [query["sql"] for query in queries if "set_config" in query["sql"]]
        self.assertEqual(len(applied), 2)
        self.assertIn("statement_timeout", applied[0])
        self.assertIn("0ms", applied[0])
        self.assertIn("work_mem", applied[1])
        self.assertIn("64MB", applied[1])

    def test_submitter_counts_do_not_join_the_user_table(self):
        """Anonymous submitters are matched by id, not by username per row."""
        self._submit(self.collector)
        self._submit(None)
        with CaptureQueriesContext(connection) as queries:
            rows = self._report()
        self._assert_metrics(rows[self.org.pk], collectors=1, active=1, submissions=2)
        aggregates = [
            query["sql"] for query in queries if "logger_instance" in query["sql"]
        ]
        self.assertEqual(len(aggregates), 3)
        for sql in aggregates:
            self.assertNotIn("auth_user", sql)
            self.assertNotIn("username", sql)

    @override_settings(
        STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}}
    )
    def test_storage_staging_honours_the_requested_temporary_directory(self):
        """The staged CSV lands where the operator points it, not only in /tmp."""
        with TemporaryDirectory() as directory:
            for tmp_dir, expected in ((directory, directory), (None, None)):
                with (
                    self.subTest(tmp_dir=tmp_dir),
                    patch.object(
                        report_account_usage,
                        "TemporaryFile",
                        wraps=report_account_usage.TemporaryFile,
                    ) as staging,
                ):
                    self._report(storage="report.csv", tmp_dir=tmp_dir)
                staging.assert_called_once_with(dir=expected)
