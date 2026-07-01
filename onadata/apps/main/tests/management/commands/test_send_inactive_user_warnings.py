# -*- coding: utf-8 -*-
"""
Test inactive-user warning command.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from onadata.apps.main.models.user_activity import UserActivity
from onadata.apps.main.models.user_deactivation import (
    UserDeactivationState,
    sync_user_deactivation_state,
)
from onadata.apps.main.tests.test_base import TestBase


class TestSendInactiveUserWarningsCommand(TestBase):
    """Test send_inactive_user_warnings management command."""

    def _set_last_activity(self, user, last_activity):
        UserActivity.objects.update_or_create(
            user=user,
            defaults={"last_activity": last_activity},
        )
        return sync_user_deactivation_state(user)

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30, 7],
        DEPLOYMENT_NAME="Command Test",
        SUPPORT_EMAIL="support@example.com",
    )
    @patch(
        "onadata.apps.main.management.commands.send_inactive_user_warnings."
        "send_account_deactivation_email.apply_async"
    )
    def test_queues_due_warning_and_marks_offsets(self, mock_apply_async):
        now = timezone.now()
        warning_user = User.objects.create_user(
            username="warning-command",
            email="warning-command@example.com",
        )
        state = self._set_last_activity(
            warning_user,
            now - timedelta(days=360),
        )
        output = StringIO()

        with patch(
            "onadata.apps.main.management.commands.send_inactive_user_warnings."
            "timezone.now",
            return_value=now,
        ):
            call_command("send_inactive_user_warnings", stdout=output)

        state.refresh_from_db()
        self.assertEqual(state.warned_offsets, [30])
        self.assertEqual(state.first_warning_sent_at, now)
        self.assertEqual(state.deactivation_scheduled_at, now + timedelta(days=30))
        self.assertIn("Queued 1 inactive-account warning emails", output.getvalue())
        mock_apply_async.assert_called_once()
        kwargs = mock_apply_async.call_args.kwargs
        email, message_txt, subject = kwargs["args"]
        self.assertEqual(email, "warning-command@example.com")
        self.assertIn("Hi warning-command", message_txt)
        self.assertIn("in 30 days", message_txt)
        self.assertIn("support@example.com", message_txt)
        self.assertEqual(subject, "Command Test account scheduled for deactivation")

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30],
    )
    @patch(
        "onadata.apps.main.management.commands.send_inactive_user_warnings."
        "send_account_deactivation_email.apply_async"
    )
    def test_dry_run_does_not_queue_or_mark_offsets(self, mock_apply_async):
        now = timezone.now()
        warning_user = User.objects.create_user(
            username="warning-command-dry-run",
            email="warning-command-dry-run@example.com",
        )
        state = self._set_last_activity(
            warning_user,
            now - timedelta(days=340),
        )
        output = StringIO()

        with patch(
            "onadata.apps.main.management.commands.send_inactive_user_warnings."
            "timezone.now",
            return_value=now,
        ):
            call_command("send_inactive_user_warnings", "--dry-run", stdout=output)

        state.refresh_from_db()
        self.assertEqual(state.warned_offsets, [])
        self.assertIsNone(state.first_warning_sent_at)
        self.assertIn(
            "Would queue 1 inactive-account warning emails", output.getvalue()
        )
        mock_apply_async.assert_not_called()

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30],
    )
    @patch(
        "onadata.apps.main.management.commands.send_inactive_user_warnings."
        "send_account_deactivation_email.apply_async"
    )
    def test_skips_due_warning_without_email(self, mock_apply_async):
        now = timezone.now()
        warning_user = User.objects.create_user(username="warning-command-no-email")
        state = self._set_last_activity(
            warning_user,
            now - timedelta(days=340),
        )
        output = StringIO()

        with patch(
            "onadata.apps.main.management.commands.send_inactive_user_warnings."
            "timezone.now",
            return_value=now,
        ):
            call_command("send_inactive_user_warnings", stdout=output)

        state = UserDeactivationState.objects.get(pk=state.pk)
        self.assertEqual(state.warned_offsets, [])
        self.assertIsNone(state.first_warning_sent_at)
        self.assertIn("skipped 1", output.getvalue())
        mock_apply_async.assert_not_called()
