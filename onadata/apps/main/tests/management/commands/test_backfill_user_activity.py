# -*- coding: utf-8 -*-
"""
Test historical user activity backfill command.
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


class TestBackfillUserActivityCommand(TestBase):
    """Test backfill_user_activity management command."""

    def setUp(self):
        super().setUp()
        self.owner = self._create_user(
            "activity-backfill-owner", "password", create_profile=True
        )
        data_dictionary = self._publish_markdown(
            TEST_FORM_MARKDOWN,
            self.owner,
            id_string="activity_backfill_form",
            title="activity_backfill_form",
        )
        self.xform = XForm.objects.get(pk=data_dictionary.pk)
        self.survey_type, _ = SurveyType.objects.get_or_create(
            slug="activity-backfill-command"
        )

    def _create_instance(self, submitter, submitted_at, editor=None, edited_at=None):
        return Instance.objects.create(
            xform=self.xform,
            user=submitter,
            survey_type=self.survey_type,
            xml=(
                f'<data id="{self.xform.id_string}">'
                f"<question>{uuid4()}</question></data>"
            ),
            uuid=str(uuid4()),
            date_created=submitted_at,
            date_modified=submitted_at,
            last_edited=edited_at,
            last_edited_by=editor,
        )

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_creates_activity_and_state_from_latest_historical_signal(self):
        now = timezone.now()
        old_activity = now - timedelta(days=400)
        login_activity = now - timedelta(days=10)
        submission_activity = now - timedelta(days=3)
        edit_activity = now - timedelta(days=1)
        user = User.objects.create_user(username="missing-activity-user")
        User.objects.filter(pk=user.pk).update(
            date_joined=old_activity,
            last_login=login_activity,
        )
        user.refresh_from_db()
        UserActivity.objects.filter(user=user).delete()
        UserDeactivationState.objects.filter(user=user).delete()
        self._create_instance(user, submission_activity)
        self._create_instance(self.owner, now - timedelta(days=20), user, edit_activity)

        call_command("backfill_user_activity", verbosity=0)

        activity = UserActivity.objects.get(user=user)
        state = UserDeactivationState.objects.get(user=user)
        self.assertEqual(activity.last_activity, edit_activity)
        self.assertEqual(
            state.deactivation_scheduled_at,
            edit_activity + timedelta(days=365),
        )

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_updates_existing_activity_and_resets_warning_state(self):
        now = timezone.now()
        user = User.objects.create_user(username="stale-activity-user")
        old_activity = now - timedelta(days=400)
        submission_activity = now - timedelta(days=2)
        User.objects.filter(pk=user.pk).update(
            date_joined=old_activity,
            last_login=None,
        )
        user.refresh_from_db()
        UserActivity.objects.filter(user=user).update(last_activity=old_activity)
        state = sync_user_deactivation_state(user)
        state.mark_warning_sent(30, when=now - timedelta(days=1))
        self._create_instance(user, submission_activity)

        call_command("backfill_user_activity", batch_size=1, verbosity=0)

        user.activity.refresh_from_db()
        state.refresh_from_db()
        self.assertEqual(user.activity.last_activity, submission_activity)
        self.assertEqual(
            state.deactivation_scheduled_at,
            submission_activity + timedelta(days=365),
        )
        self.assertEqual(state.warned_offsets, [])
        self.assertIsNone(state.first_warning_sent_at)

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_does_not_move_newer_activity_backwards_or_clear_warning_state(self):
        now = timezone.now()
        user = User.objects.create_user(username="newer-activity-user")
        newer_activity = now - timedelta(days=1)
        older_submission = now - timedelta(days=20)
        User.objects.filter(pk=user.pk).update(
            date_joined=now - timedelta(days=300),
            last_login=None,
        )
        user.refresh_from_db()
        UserActivity.objects.filter(user=user).update(last_activity=newer_activity)
        state = sync_user_deactivation_state(user)
        state.mark_warning_sent(7, when=now)
        self._create_instance(user, older_submission)

        call_command("backfill_user_activity", verbosity=0)

        user.activity.refresh_from_db()
        state.refresh_from_db()
        self.assertEqual(user.activity.last_activity, newer_activity)
        self.assertEqual(
            state.deactivation_scheduled_at,
            newer_activity + timedelta(days=365),
        )
        self.assertEqual(state.warned_offsets, [7])
        self.assertEqual(state.first_warning_sent_at, now)

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_batch_resume_and_dry_run_controls(self):
        now = timezone.now()
        first_user = User.objects.create_user(username="first-user-batch")
        second_user = User.objects.create_user(username="second-user-batch")
        old_activity = now - timedelta(days=300)
        submitted_at = now - timedelta(days=2)
        for user in (first_user, second_user):
            User.objects.filter(pk=user.pk).update(
                date_joined=old_activity,
                last_login=None,
            )
            user.refresh_from_db()
            UserActivity.objects.filter(user=user).update(last_activity=old_activity)
            self._create_instance(user, submitted_at)

        call_command(
            "backfill_user_activity",
            start_after_user_id=first_user.pk,
            batch_size=1,
            max_users=1,
            dry_run=True,
            verbosity=0,
        )

        first_user.activity.refresh_from_db()
        second_user.activity.refresh_from_db()
        self.assertEqual(first_user.activity.last_activity, old_activity)
        self.assertEqual(second_user.activity.last_activity, old_activity)

        call_command(
            "backfill_user_activity",
            start_after_user_id=first_user.pk,
            batch_size=1,
            max_users=1,
            verbosity=0,
        )

        first_user.activity.refresh_from_db()
        second_user.activity.refresh_from_db()
        self.assertEqual(first_user.activity.last_activity, old_activity)
        self.assertEqual(second_user.activity.last_activity, submitted_at)
