# -*- coding: utf-8 -*-
"""
Test reactivate inactive user management command.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
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


class TestReactivateInactiveUserCommand(TestBase):
    """Test reactivate_inactive_user management command."""

    def _create_current_deactivation(self, username, when):
        user = User.objects.create_user(username=username, is_active=False)
        UserActivity.objects.filter(user=user).update(
            last_activity=when - timedelta(days=400)
        )
        state = sync_user_deactivation_state(user)
        state.deactivated_at = when - timedelta(days=1)
        state.first_warning_sent_at = when - timedelta(days=31)
        state.warned_offsets = [30]
        state.permission_policy_applied = PERMISSION_POLICY_REVOKE
        state.save(
            update_fields=[
                "deactivated_at",
                "first_warning_sent_at",
                "warned_offsets",
                "permission_policy_applied",
            ]
        )
        Token.objects.filter(user=user).delete()
        TempToken.objects.filter(user=user).delete()

        return user, state

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_reactivates_user_by_username(self):
        now = timezone.now()
        user, state = self._create_current_deactivation("command-reactivate", now)
        output = StringIO()

        with patch(
            "onadata.apps.main.management.commands.reactivate_inactive_user."
            "timezone.now",
            return_value=now,
        ):
            call_command("reactivate_inactive_user", user.username, stdout=output)

        user.refresh_from_db()
        state.refresh_from_db()
        self.assertIn("Reactivated command-reactivate.", output.getvalue())
        self.assertIn("Reactivated 1 inactive users; skipped 0.", output.getvalue())
        self.assertTrue(user.is_active)
        self.assertTrue(Token.objects.filter(user=user).exists())
        self.assertTrue(TempToken.objects.filter(user=user).exists())
        self.assertEqual(user.activity.last_activity, now)
        self.assertEqual(state.reactivated_at, now)
        self.assertEqual(state.deactivation_scheduled_at, now + timedelta(days=365))
        self.assertIsNone(state.first_warning_sent_at)
        self.assertEqual(state.warned_offsets, [])

    def test_reactivates_user_by_id(self):
        now = timezone.now()
        user, state = self._create_current_deactivation("command-reactivate-id", now)

        with patch(
            "onadata.apps.main.management.commands.reactivate_inactive_user."
            "timezone.now",
            return_value=now,
        ):
            call_command("reactivate_inactive_user", user.pk, verbosity=0)

        user.refresh_from_db()
        state.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(state.reactivated_at, now)

    def test_rejects_ambiguous_numeric_identifier(self):
        now = timezone.now()
        id_user, _ = self._create_current_deactivation("command-id-target", now)
        username_user, _ = self._create_current_deactivation(str(id_user.pk), now)

        with self.assertRaises(CommandError) as context:
            call_command("reactivate_inactive_user", str(id_user.pk), verbosity=0)

        self.assertIn("Ambiguous numeric user identifier", str(context.exception))
        id_user.refresh_from_db()
        username_user.refresh_from_db()
        self.assertFalse(id_user.is_active)
        self.assertFalse(username_user.is_active)

    def test_dry_run_does_not_mutate_user(self):
        now = timezone.now()
        user, state = self._create_current_deactivation("command-dry-run", now)
        output = StringIO()

        with patch(
            "onadata.apps.main.management.commands.reactivate_inactive_user."
            "timezone.now",
            return_value=now,
        ):
            call_command(
                "reactivate_inactive_user",
                user.username,
                "--dry-run",
                stdout=output,
            )

        user.refresh_from_db()
        state.refresh_from_db()
        self.assertIn("Would reactivate command-dry-run.", output.getvalue())
        self.assertFalse(user.is_active)
        self.assertIsNone(state.reactivated_at)
        self.assertFalse(Token.objects.filter(user=user).exists())
        self.assertFalse(TempToken.objects.filter(user=user).exists())

    def test_skips_user_without_current_deactivation(self):
        user = User.objects.create_user(username="command-skip")
        state = sync_user_deactivation_state(user)
        output = StringIO()

        call_command("reactivate_inactive_user", user.username, stdout=output)

        state.refresh_from_db()
        self.assertIn(
            "Skipped command-skip: not currently deactivated.", output.getvalue()
        )
        self.assertIsNone(state.reactivated_at)

    def test_skips_user_without_lifecycle_state(self):
        user = User.objects.create_user(username="command-no-state")
        UserDeactivationState.objects.filter(user=user).delete()
        output = StringIO()

        call_command("reactivate_inactive_user", user.username, stdout=output)

        self.assertIn(
            "Skipped command-no-state: no lifecycle state.", output.getvalue()
        )

    def test_rejects_unknown_user(self):
        with self.assertRaises(CommandError):
            call_command("reactivate_inactive_user", "missing-reactivation-user")
