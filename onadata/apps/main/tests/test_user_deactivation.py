# -*- coding: utf-8 -*-
"""
Test user deactivation lifecycle state.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.main.models.user_activity import UserActivity, record_user_activity
from onadata.apps.main.models.user_deactivation import (
    PERMISSION_POLICY_REVOKE,
    UserDeactivationState,
    get_deactivation_permission_policy,
    get_deactivation_states_due_for_deactivation,
    get_deactivation_states_due_for_warning,
    get_deactivation_warning_days,
    sync_user_deactivation_state,
)


class TestUserDeactivationState(TestCase):
    """Test inactive account lifecycle state helpers."""

    def _create_due_state(self, user, when, warning_sent_at=None):
        last_activity = when - timedelta(days=366)
        UserActivity.objects.filter(user=user).update(last_activity=last_activity)
        state = sync_user_deactivation_state(user)
        state.deactivation_scheduled_at = when - timedelta(seconds=1)
        state.save(update_fields=["deactivation_scheduled_at"])

        if warning_sent_at is not None:
            state.mark_warning_sent(30, when=warning_sent_at)

        return state

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_user_deactivation_state_created_for_new_user_activity(self):
        user = User.objects.create_user(username="new-lifecycle-user")

        self.assertEqual(user.deactivation_state.user, user)
        self.assertEqual(
            user.deactivation_state.deactivation_scheduled_at,
            user.activity.last_activity + timedelta(days=365),
        )

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_sync_user_deactivation_state_schedules_from_activity(self):
        now = timezone.now()
        user = User.objects.create_user(username="inactive-alice")
        last_activity = now - timedelta(days=300)
        UserActivity.objects.filter(user=user).update(last_activity=last_activity)

        state = sync_user_deactivation_state(user)

        self.assertEqual(state.user, user)
        self.assertEqual(
            state.deactivation_scheduled_at,
            last_activity + timedelta(days=365),
        )
        self.assertEqual(state.warned_offsets, [])
        self.assertIsNone(state.first_warning_sent_at)

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30, 7],
    )
    def test_sync_user_deactivation_state_applies_warning_grace(self):
        now = timezone.now()
        user = User.objects.create_user(username="overdue-lifecycle-user")
        last_activity = now - timedelta(days=400)
        UserActivity.objects.filter(user=user).update(last_activity=last_activity)

        before = timezone.now()
        state = sync_user_deactivation_state(user)
        after = timezone.now()

        self.assertGreaterEqual(
            state.deactivation_scheduled_at,
            before + timedelta(days=30),
        )
        self.assertLessEqual(
            state.deactivation_scheduled_at,
            after + timedelta(days=30),
        )
        self.assertEqual(state.warned_offsets, [])
        self.assertIsNone(state.first_warning_sent_at)

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_activity_update_creates_missing_deactivation_state(self):
        now = timezone.now()
        user = User.objects.create_user(username="missing-lifecycle-state")
        UserDeactivationState.objects.filter(user=user).delete()

        new_activity = now + timedelta(hours=1)
        record_user_activity(user, when=new_activity, force=True)

        state = UserDeactivationState.objects.get(user=user)
        self.assertEqual(
            state.deactivation_scheduled_at,
            new_activity + timedelta(days=365),
        )

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_activity_update_resets_existing_warning_state(self):
        now = timezone.now()
        user = User.objects.create_user(username="warned-alice")
        last_activity = now - timedelta(days=340)
        UserActivity.objects.filter(user=user).update(last_activity=last_activity)
        state = sync_user_deactivation_state(user)
        state.mark_warning_sent(30, when=now)

        new_activity = now + timedelta(hours=1)
        record_user_activity(user, when=new_activity, force=True)
        state.refresh_from_db()

        self.assertEqual(
            state.deactivation_scheduled_at,
            new_activity + timedelta(days=365),
        )
        self.assertEqual(state.warned_offsets, [])
        self.assertIsNone(state.first_warning_sent_at)

    def test_mark_warning_sent_tracks_first_warning_and_offsets(self):
        user = User.objects.create_user(username="warning-state")
        state = sync_user_deactivation_state(user)
        warning_at = timezone.now()

        state.mark_warning_sent(7, when=warning_at)
        state.mark_warning_sent(30, when=warning_at + timedelta(days=1))
        state.refresh_from_db()

        self.assertEqual(state.first_warning_sent_at, warning_at)
        self.assertEqual(state.warned_offsets, [30, 7])

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365)
    def test_due_for_warning_selector_uses_schedule_and_offsets(self):
        now = timezone.now()
        user = User.objects.create_user(username="warning-due")
        last_activity = now - timedelta(days=340)
        UserActivity.objects.filter(user=user).update(last_activity=last_activity)
        state = sync_user_deactivation_state(user)

        self.assertTrue(
            get_deactivation_states_due_for_warning(30, when=now)
            .filter(pk=state.pk)
            .exists()
        )
        self.assertFalse(
            get_deactivation_states_due_for_warning(7, when=now)
            .filter(pk=state.pk)
            .exists()
        )

        state.mark_warning_sent(30, when=now)

        self.assertFalse(
            get_deactivation_states_due_for_warning(30, when=now)
            .filter(pk=state.pk)
            .exists()
        )

    @override_settings(DEACTIVATION_INACTIVITY_DAYS=365, DEACTIVATION_WARNING_DAYS=[])
    def test_due_for_deactivation_selector_excludes_processed_users(self):
        now = timezone.now()
        user = User.objects.create_user(username="deactivation-due")
        last_activity = now - timedelta(days=366)
        UserActivity.objects.filter(user=user).update(last_activity=last_activity)
        state = sync_user_deactivation_state(user)

        self.assertTrue(
            get_deactivation_states_due_for_deactivation(when=now)
            .filter(pk=state.pk)
            .exists()
        )

        state.deactivated_at = now
        state.save(update_fields=["deactivated_at"])

        self.assertFalse(
            get_deactivation_states_due_for_deactivation(when=now)
            .filter(pk=state.pk)
            .exists()
        )

        state.reactivated_at = now + timedelta(seconds=1)
        state.save(update_fields=["reactivated_at"])

        self.assertTrue(
            get_deactivation_states_due_for_deactivation(when=now)
            .filter(pk=state.pk)
            .exists()
        )

        state.reactivated_at = None
        state.deactivated_at = None
        state.save(update_fields=["deactivated_at", "reactivated_at"])
        user.is_active = False
        user.save(update_fields=["is_active"])

        self.assertFalse(
            get_deactivation_states_due_for_deactivation(when=now)
            .filter(pk=state.pk)
            .exists()
        )

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30, 7],
    )
    def test_due_for_deactivation_requires_mature_warning(self):
        now = timezone.now()
        user = User.objects.create_user(username="warning-required")
        state = self._create_due_state(user, now)

        self.assertFalse(
            get_deactivation_states_due_for_deactivation(when=now)
            .filter(pk=state.pk)
            .exists()
        )

        state.mark_warning_sent(30, when=now - timedelta(days=10))

        self.assertFalse(
            get_deactivation_states_due_for_deactivation(when=now)
            .filter(pk=state.pk)
            .exists()
        )

        state.first_warning_sent_at = now - timedelta(days=31)
        state.save(update_fields=["first_warning_sent_at"])

        self.assertTrue(
            get_deactivation_states_due_for_deactivation(when=now)
            .filter(pk=state.pk)
            .exists()
        )

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30],
        DEACTIVATION_EXCLUDED_USERNAMES=["allowlisted-user"],
    )
    def test_due_for_deactivation_excludes_protected_accounts(self):
        now = timezone.now()
        normal_user = User.objects.create_user(username="normal-due")
        staff_user = User.objects.create_user(username="staff-due", is_staff=True)
        superuser = User.objects.create_user(
            username="superuser-due", is_superuser=True
        )
        allowlisted_user = User.objects.create_user(username="allowlisted-user")
        id_allowlisted_user = User.objects.create_user(username="id-allowlisted-user")
        org_creator = User.objects.create_user(username="org-creator")
        org_user = User.objects.create_user(username="org-account")
        OrganizationProfile.objects.create(
            user=org_user, name="Org Account", creator=org_creator
        )

        states = {
            user.username: self._create_due_state(
                user, now, warning_sent_at=now - timedelta(days=31)
            )
            for user in (
                normal_user,
                staff_user,
                superuser,
                allowlisted_user,
                id_allowlisted_user,
                org_user,
            )
        }

        with override_settings(DEACTIVATION_EXCLUDED_USER_IDS=[id_allowlisted_user.pk]):
            due_state_ids = set(
                get_deactivation_states_due_for_deactivation(when=now).values_list(
                    "pk", flat=True
                )
            )

        self.assertIn(states["normal-due"].pk, due_state_ids)
        self.assertNotIn(states["staff-due"].pk, due_state_ids)
        self.assertNotIn(states["superuser-due"].pk, due_state_ids)
        self.assertNotIn(states["allowlisted-user"].pk, due_state_ids)
        self.assertNotIn(states["id-allowlisted-user"].pk, due_state_ids)
        self.assertNotIn(states["org-account"].pk, due_state_ids)

    @override_settings(DEACTIVATION_WARNING_DAYS=[7, 30, 30, -1])
    def test_deactivation_warning_days_are_normalized(self):
        self.assertEqual(get_deactivation_warning_days(), (30, 7))

    def test_deactivation_permission_policy_defaults_to_revoke(self):
        self.assertEqual(get_deactivation_permission_policy(), PERMISSION_POLICY_REVOKE)

    @override_settings(DEACTIVATION_PERMISSION_POLICY="invalid")
    def test_deactivation_permission_policy_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            get_deactivation_permission_policy()

    def test_sync_user_deactivation_state_ignores_non_users(self):
        count_before = UserDeactivationState.objects.count()

        self.assertIsNone(sync_user_deactivation_state(None))
        self.assertEqual(UserDeactivationState.objects.count(), count_before)
