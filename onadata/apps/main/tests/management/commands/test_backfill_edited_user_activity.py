# -*- coding: utf-8 -*-
"""
Test edited-submission activity backfill command.
"""

from datetime import timedelta
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from onadata.apps.logger.models import Instance, SurveyType, XForm
from onadata.apps.main.models.user_activity import UserActivity
from onadata.apps.main.models.user_deactivation import (
    UserDeactivationState,
    sync_user_deactivation_state,
)
from onadata.apps.main.tests.test_base import TestBase

TEST_FORM_MARKDOWN = """
| survey |
|        | type | name     | label    |
|        | text | question | Question |
"""


class TestBackfillEditedUserActivityCommand(TestBase):
    """Test backfill_edited_user_activity management command."""

    def setUp(self):
        super().setUp()
        self.owner = self._create_user(
            "edited-activity-owner", "password", create_profile=True
        )
        data_dictionary = self._publish_markdown(
            TEST_FORM_MARKDOWN,
            self.owner,
            id_string="edited_activity_form",
            title="edited_activity_form",
        )
        self.xform = XForm.objects.get(pk=data_dictionary.pk)
        self.survey_type, _ = SurveyType.objects.get_or_create(
            slug="edited-activity-command"
        )

    def _create_edited_instance(self, editor, edited_at):
        return Instance.objects.create(
            xform=self.xform,
            user=self.owner,
            survey_type=self.survey_type,
            xml=(
                f'<data id="{self.xform.id_string}">'
                f"<question>{uuid4()}</question></data>"
            ),
            uuid=str(uuid4()),
            last_edited=edited_at,
            last_edited_by=editor,
        )

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30, 7],
    )
    def test_updates_activity_and_deactivation_state_from_latest_edit(self):
        now = timezone.now()
        editor = User.objects.create_user(username="stale-editor")
        old_activity = now - timedelta(days=400)
        latest_edit = now - timedelta(days=3)
        UserActivity.objects.filter(user=editor).update(last_activity=old_activity)
        state = sync_user_deactivation_state(editor)
        state.mark_warning_sent(30, when=now - timedelta(days=1))
        self._create_edited_instance(editor, now - timedelta(days=10))
        self._create_edited_instance(editor, latest_edit)

        call_command("backfill_edited_user_activity", batch_size=1, verbosity=0)

        editor.activity.refresh_from_db()
        state.refresh_from_db()
        self.assertEqual(editor.activity.last_activity, latest_edit)
        self.assertEqual(
            state.deactivation_scheduled_at,
            latest_edit + timedelta(days=365),
        )
        self.assertEqual(state.warned_offsets, [])
        self.assertIsNone(state.first_warning_sent_at)

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_creates_missing_activity_and_deactivation_state(self):
        now = timezone.now()
        editor = User.objects.create_user(username="missing-activity-editor")
        UserActivity.objects.filter(user=editor).delete()
        UserDeactivationState.objects.filter(user=editor).delete()
        edited_at = now - timedelta(days=2)
        self._create_edited_instance(editor, edited_at)

        call_command("backfill_edited_user_activity", verbosity=0)

        activity = UserActivity.objects.get(user=editor)
        state = UserDeactivationState.objects.get(user=editor)
        self.assertEqual(activity.last_activity, edited_at)
        self.assertEqual(
            state.deactivation_scheduled_at,
            edited_at + timedelta(days=365),
        )

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_does_not_move_newer_activity_backwards_or_clear_warning_state(self):
        now = timezone.now()
        editor = User.objects.create_user(username="newer-activity-editor")
        newer_activity = now - timedelta(days=1)
        older_edit = now - timedelta(days=10)
        UserActivity.objects.filter(user=editor).update(last_activity=newer_activity)
        state = sync_user_deactivation_state(editor)
        state.mark_warning_sent(7, when=now)
        self._create_edited_instance(editor, older_edit)

        call_command("backfill_edited_user_activity", verbosity=0)

        editor.activity.refresh_from_db()
        state.refresh_from_db()
        self.assertEqual(editor.activity.last_activity, newer_activity)
        self.assertEqual(
            state.deactivation_scheduled_at,
            newer_activity + timedelta(days=365),
        )
        self.assertEqual(state.warned_offsets, [7])
        self.assertEqual(state.first_warning_sent_at, now)

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30, 7],
    )
    def test_does_not_reapply_warning_grace_when_activity_is_unchanged(self):
        now = timezone.now()
        editor = User.objects.create_user(username="unchanged-overdue-editor")
        activity_at = now - timedelta(days=400)
        older_edit = now - timedelta(days=450)
        scheduled_at = now - timedelta(days=1)
        warning_at = now - timedelta(days=31)
        UserActivity.objects.filter(user=editor).update(last_activity=activity_at)
        state = sync_user_deactivation_state(editor)
        state.deactivation_scheduled_at = scheduled_at
        state.first_warning_sent_at = warning_at
        state.warned_offsets = [30]
        state.save(
            update_fields=[
                "deactivation_scheduled_at",
                "first_warning_sent_at",
                "warned_offsets",
            ]
        )
        self._create_edited_instance(editor, older_edit)

        call_command("backfill_edited_user_activity", verbosity=0)

        editor.activity.refresh_from_db()
        state.refresh_from_db()
        self.assertEqual(editor.activity.last_activity, activity_at)
        self.assertEqual(state.deactivation_scheduled_at, scheduled_at)
        self.assertEqual(state.first_warning_sent_at, warning_at)
        self.assertEqual(state.warned_offsets, [30])

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_batch_resume_and_dry_run_controls(self):
        now = timezone.now()
        first_editor = User.objects.create_user(username="first-batch-editor")
        second_editor = User.objects.create_user(username="second-batch-editor")
        edited_at = now - timedelta(days=2)
        for editor in (first_editor, second_editor):
            UserActivity.objects.filter(user=editor).update(
                last_activity=now - timedelta(days=300)
            )
            self._create_edited_instance(editor, edited_at)

        call_command(
            "backfill_edited_user_activity",
            start_after_user_id=first_editor.pk,
            batch_size=1,
            max_users=1,
            dry_run=True,
            verbosity=0,
        )

        first_editor.activity.refresh_from_db()
        second_editor.activity.refresh_from_db()
        self.assertNotEqual(second_editor.activity.last_activity, edited_at)

        call_command(
            "backfill_edited_user_activity",
            start_after_user_id=first_editor.pk,
            batch_size=1,
            max_users=1,
            verbosity=0,
        )

        first_editor.activity.refresh_from_db()
        second_editor.activity.refresh_from_db()
        self.assertNotEqual(first_editor.activity.last_activity, edited_at)
        self.assertEqual(second_editor.activity.last_activity, edited_at)
