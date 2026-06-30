# -*- coding: utf-8 -*-
"""
Test deactivate inactive users management command.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from rest_framework.authtoken.models import Token

from onadata.apps.api.models.temp_token import TempToken
from onadata.apps.main.models.user_activity import UserActivity
from onadata.apps.main.models.user_deactivation import (
    PERMISSION_POLICY_REVOKE,
    UserDeactivationState,
    sync_user_deactivation_state,
)
from onadata.apps.main.tests.test_base import TestBase


class TestDeactivateInactiveUsersCommand(TestBase):
    """Test deactivate_inactive_users management command."""

    def _set_last_activity(self, user, last_activity):
        UserActivity.objects.update_or_create(
            user=user,
            defaults={"last_activity": last_activity},
        )
        return sync_user_deactivation_state(user)

    def _create_due_deactivation_state(self, username, when):
        user = User.objects.create_user(username=username)
        state = self._set_last_activity(user, when - timedelta(days=366))
        state.deactivation_scheduled_at = when - timedelta(seconds=1)
        state.first_warning_sent_at = when - timedelta(days=31)
        state.warned_offsets = [30]
        state.save(
            update_fields=[
                "deactivation_scheduled_at",
                "first_warning_sent_at",
                "warned_offsets",
            ]
        )
        Token.objects.get_or_create(user=user)
        TempToken.objects.get_or_create(user=user)

        return user, state

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30],
        DEACTIVATION_PERMISSION_POLICY="revoke",
    )
    def test_deactivates_due_users(self):
        now = timezone.now()
        user, state = self._create_due_deactivation_state(
            "deactivate-command",
            now,
        )
        output = StringIO()

        with patch(
            "onadata.apps.main.management.commands.deactivate_inactive_users."
            "timezone.now",
            return_value=now,
        ):
            call_command("deactivate_inactive_users", stdout=output)

        user.refresh_from_db()
        state.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertFalse(Token.objects.filter(user=user).exists())
        self.assertFalse(TempToken.objects.filter(user=user).exists())
        self.assertEqual(state.deactivated_at, now)
        self.assertEqual(state.permissions_revoked_at, now)
        self.assertEqual(state.permission_policy_applied, PERMISSION_POLICY_REVOKE)
        self.assertIn("Deactivated 1 inactive users; skipped 0", output.getvalue())
        self.assertIn("revoked 2 tokens", output.getvalue())

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30],
    )
    def test_dry_run_does_not_deactivate_due_users(self):
        now = timezone.now()
        user, state = self._create_due_deactivation_state(
            "deactivate-command-dry-run",
            now,
        )
        output = StringIO()

        with patch(
            "onadata.apps.main.management.commands.deactivate_inactive_users."
            "timezone.now",
            return_value=now,
        ):
            call_command("deactivate_inactive_users", "--dry-run", stdout=output)

        user.refresh_from_db()
        state.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(Token.objects.filter(user=user).exists())
        self.assertTrue(TempToken.objects.filter(user=user).exists())
        self.assertIsNone(state.deactivated_at)
        self.assertIn("Would deactivate 1 inactive users.", output.getvalue())

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30, 7],
    )
    def test_ignores_due_warning_actions(self):
        now = timezone.now()
        warning_user = User.objects.create_user(username="deactivate-command-warning")
        warning_state = self._set_last_activity(
            warning_user,
            now - timedelta(days=360),
        )
        output = StringIO()

        with patch(
            "onadata.apps.main.management.commands.deactivate_inactive_users."
            "timezone.now",
            return_value=now,
        ):
            call_command("deactivate_inactive_users", "--dry-run", stdout=output)

        warning_user.refresh_from_db()
        warning_state = UserDeactivationState.objects.get(pk=warning_state.pk)
        self.assertTrue(warning_user.is_active)
        self.assertIsNone(warning_state.deactivated_at)
        self.assertIn("Would deactivate 0 inactive users.", output.getvalue())
