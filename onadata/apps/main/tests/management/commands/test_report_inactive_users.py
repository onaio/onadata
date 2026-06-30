# -*- coding: utf-8 -*-
"""
Test inactive-user report command.
"""

import csv
import os
from datetime import timedelta
from io import StringIO
from tempfile import NamedTemporaryFile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from onadata.apps.main.models.user_activity import UserActivity
from onadata.apps.main.models.user_deactivation import (
    DEACTIVATION_ACTION_DEACTIVATE,
    DEACTIVATION_ACTION_SEND_WARNING,
    DEACTIVATION_REPORT_COHORT_DUE_DEACTIVATION,
    DEACTIVATION_REPORT_COHORT_DUE_WARNING,
    DEACTIVATION_REPORT_COLUMNS,
    UserDeactivationState,
    sync_user_deactivation_state,
)
from onadata.apps.main.tests.test_base import TestBase


class TestReportInactiveUsersCommand(TestBase):
    """Test report_inactive_users management command."""

    def _set_last_activity(self, user, last_activity):
        UserActivity.objects.update_or_create(
            user=user,
            defaults={"last_activity": last_activity},
        )
        return sync_user_deactivation_state(user)

    def _read_csv(self, csv_content):
        reader = csv.DictReader(StringIO(csv_content))
        return reader.fieldnames, list(reader)

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30, 7],
        DEACTIVATION_PERMISSION_POLICY="revoke",
    )
    def test_writes_report_csv_to_stdout(self):
        now = timezone.now()
        warning_user = User.objects.create_user(
            username="report-command-warning",
            email="report-command-warning@example.com",
            first_name="Report",
            last_name="Command",
        )
        warning_activity = now - timedelta(days=360)
        self._set_last_activity(warning_user, warning_activity)
        output = StringIO()

        with patch(
            "onadata.apps.main.management.commands.report_inactive_users."
            "timezone.now",
            return_value=now,
        ):
            call_command("report_inactive_users", window_days=30, stdout=output)

        fieldnames, rows = self._read_csv(output.getvalue())
        rows_by_username = {row["username"]: row for row in rows}
        warning_row = rows_by_username["report-command-warning"]
        self.assertEqual(fieldnames, list(DEACTIVATION_REPORT_COLUMNS))
        self.assertEqual(warning_row["email"], "report-command-warning@example.com")
        self.assertEqual(warning_row["display_name"], "Report Command")
        self.assertEqual(
            warning_row["computed_last_activity"],
            warning_activity.isoformat(),
        )
        self.assertEqual(
            warning_row["deactivation_scheduled_at"],
            (warning_activity + timedelta(days=365)).isoformat(),
        )
        self.assertEqual(warning_row["cohort"], DEACTIVATION_REPORT_COHORT_DUE_WARNING)
        self.assertEqual(warning_row["next_action"], DEACTIVATION_ACTION_SEND_WARNING)
        self.assertEqual(warning_row["next_action_date"], now.isoformat())
        self.assertEqual(warning_row["warnings_sent"], "")
        self.assertEqual(warning_row["permission_policy"], "revoke")
        self.assertEqual(
            warning_row["dry_run_action_summary"],
            "would send 30-day warning email",
        )

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30],
        DEACTIVATION_PERMISSION_POLICY="revoke",
    )
    def test_writes_report_csv_escapes_formula_values(self):
        now = timezone.now()
        warning_user = User.objects.create_user(
            username="+report-formula",
            email="-report-formula@example.com",
            first_name="=Report",
            last_name="Formula",
        )
        self._set_last_activity(warning_user, now - timedelta(days=340))
        output = StringIO()

        with patch(
            "onadata.apps.main.management.commands.report_inactive_users."
            "timezone.now",
            return_value=now,
        ):
            call_command("report_inactive_users", window_days=30, stdout=output)

        _, rows = self._read_csv(output.getvalue())
        formula_row = next(row for row in rows if row["username"] == "'+report-formula")
        self.assertEqual(formula_row["email"], "'-report-formula@example.com")
        self.assertEqual(formula_row["display_name"], "'=Report Formula")

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30],
        DEACTIVATION_PERMISSION_POLICY="preserve",
    )
    def test_writes_report_csv_to_file(self):
        now = timezone.now()
        deactivation_user = User.objects.create_user(
            username="report-command-deactivate"
        )
        state = self._set_last_activity(
            deactivation_user,
            now - timedelta(days=366),
        )
        state.deactivation_scheduled_at = now - timedelta(seconds=1)
        state.first_warning_sent_at = now - timedelta(days=31)
        state.warned_offsets = [30]
        state.save(
            update_fields=[
                "deactivation_scheduled_at",
                "first_warning_sent_at",
                "warned_offsets",
            ]
        )
        output = StringIO()
        with NamedTemporaryFile(delete=False) as tmp_file:
            csv_path = tmp_file.name
        self.addCleanup(lambda: os.path.exists(csv_path) and os.unlink(csv_path))

        with patch(
            "onadata.apps.main.management.commands.report_inactive_users."
            "timezone.now",
            return_value=now,
        ):
            call_command(
                "report_inactive_users",
                "--csv",
                csv_path,
                window_days=30,
                stdout=output,
            )

        with open(csv_path, encoding="utf-8", newline="") as report_file:
            fieldnames, rows = self._read_csv(report_file.read())

        rows_by_username = {row["username"]: row for row in rows}
        deactivation_row = rows_by_username["report-command-deactivate"]
        self.assertEqual(fieldnames, list(DEACTIVATION_REPORT_COLUMNS))
        self.assertIn("Wrote", output.getvalue())
        self.assertEqual(
            deactivation_row["cohort"],
            DEACTIVATION_REPORT_COHORT_DUE_DEACTIVATION,
        )
        self.assertEqual(
            deactivation_row["next_action"],
            DEACTIVATION_ACTION_DEACTIVATE,
        )
        self.assertEqual(deactivation_row["permission_policy"], "preserve")
        self.assertIn(
            "would deactivate user and revoke tokens",
            deactivation_row["dry_run_action_summary"],
        )
        self.assertEqual(
            UserDeactivationState.objects.get(user=deactivation_user).deactivated_at,
            None,
        )
        deactivation_user.refresh_from_db()
        self.assertTrue(deactivation_user.is_active)

    def test_rejects_invalid_window_days(self):
        with self.assertRaises(CommandError):
            call_command("report_inactive_users", window_days=0)
