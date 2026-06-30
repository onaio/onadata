# -*- coding: utf-8 -*-
"""
Test user deactivation lifecycle state.
"""

from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone

from guardian.shortcuts import assign_perm, get_perms, remove_perm

from onadata.apps.api import tools
from onadata.apps.api.models.organization_profile import (
    get_or_create_organization_owners_team,
)
from onadata.apps.logger.models import XForm
from onadata.apps.main.models.user_activity import UserActivity, record_user_activity
from onadata.apps.main.models.user_deactivation import (
    DEACTIVATION_ACTION_DEACTIVATE,
    DEACTIVATION_ACTION_SEND_WARNING,
    DEACTIVATION_EXCLUSION_STAFF,
    DEACTIVATION_REPORT_COHORT_ALREADY_WARNED,
    DEACTIVATION_REPORT_COHORT_DUE_DEACTIVATION,
    DEACTIVATION_REPORT_COHORT_DUE_WARNING,
    DEACTIVATION_REPORT_COHORT_RECENTLY_DEACTIVATED,
    DEACTIVATION_REPORT_COHORT_RECENTLY_REACTIVATED,
    DEACTIVATION_REPORT_COHORT_SKIPPED,
    PERMISSION_POLICY_REVOKE,
    UserDeactivationPermissionSnapshot,
    UserDeactivationState,
    get_deactivation_exclusion_reason,
    get_deactivation_permission_policy,
    get_deactivation_report_rows,
    get_deactivation_states_due_for_deactivation,
    get_deactivation_states_due_for_warning,
    get_deactivation_warning_days,
    get_pending_deactivation_actions,
    snapshot_revocable_user_permissions,
    sync_user_deactivation_state,
)
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.user_auth import get_user_default_project

TEST_FORM_MARKDOWN = """
| survey |
|        | type | name     | label    |
|        | text | question | Question |
"""


class TestUserDeactivationState(TestBase):
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

    def _publish_test_form(self, user, project, id_string, created_by=None):
        data_dictionary = self._publish_markdown(
            TEST_FORM_MARKDOWN,
            user,
            project=project,
            id_string=id_string,
            title=id_string,
        )
        xform = XForm.objects.get(pk=data_dictionary.pk)
        if xform.created_by_id != getattr(created_by, "pk", None):
            xform.created_by = created_by
            xform.save(update_fields=["created_by"])

        return xform

    def _clear_user_object_permissions(self, user, *objects):
        for obj in objects:
            for codename in get_perms(user, obj):
                remove_perm(codename, user, obj)

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
        DEACTIVATION_WARNING_DAYS=[30, 7],
        DEACTIVATION_PERMISSION_POLICY="revoke",
    )
    def test_pending_deactivation_actions_builds_warning_and_deactivation_plans(self):
        now = timezone.now()
        warning_user = User.objects.create_user(username="action-warning")
        warning_activity = now - timedelta(days=360)
        UserActivity.objects.filter(user=warning_user).update(
            last_activity=warning_activity
        )
        warning_state = sync_user_deactivation_state(warning_user)
        due_user = User.objects.create_user(username="action-deactivate")
        self._create_due_state(due_user, now, warning_sent_at=now - timedelta(days=31))

        actions_by_username = {
            action.user.username: action
            for action in get_pending_deactivation_actions(when=now)
        }

        self.assertEqual(
            actions_by_username["action-warning"].action,
            DEACTIVATION_ACTION_SEND_WARNING,
        )
        self.assertEqual(actions_by_username["action-warning"].warning_offsets, (30, 7))
        self.assertEqual(
            actions_by_username["action-warning"].dry_run_action_summary,
            "would send 30-day and 7-day warning email",
        )
        self.assertEqual(
            actions_by_username["action-deactivate"].action,
            DEACTIVATION_ACTION_DEACTIVATE,
        )
        self.assertEqual(
            actions_by_username["action-deactivate"].as_report_row().cohort,
            DEACTIVATION_REPORT_COHORT_DUE_DEACTIVATION,
        )
        self.assertIn(
            "would deactivate user and revoke tokens",
            actions_by_username["action-deactivate"].dry_run_action_summary,
        )
        warning_state.refresh_from_db()
        self.assertEqual(warning_state.warned_offsets, [])

    @override_settings(
        DEACTIVATION_INACTIVITY_DAYS=365,
        DEACTIVATION_WARNING_DAYS=[30, 7],
        DEACTIVATION_PERMISSION_POLICY="revoke",
    )
    def test_deactivation_report_rows_include_action_and_status_cohorts(self):
        now = timezone.now()
        warning_user = User.objects.create_user(
            username="report-warning",
            email="report-warning@example.com",
            first_name="Report",
            last_name="Warning",
        )
        warning_activity = now - timedelta(days=360)
        UserActivity.objects.filter(user=warning_user).update(
            last_activity=warning_activity
        )
        sync_user_deactivation_state(warning_user)
        already_warned_user = User.objects.create_user(username="report-warned")
        already_warned_activity = now - timedelta(days=340)
        UserActivity.objects.filter(user=already_warned_user).update(
            last_activity=already_warned_activity
        )
        already_warned_state = sync_user_deactivation_state(already_warned_user)
        already_warned_state.mark_warning_sent(30, when=now - timedelta(days=5))
        staff_user = User.objects.create_user(username="report-staff", is_staff=True)
        UserActivity.objects.filter(user=staff_user).update(
            last_activity=warning_activity
        )
        sync_user_deactivation_state(staff_user)
        deactivated_user = User.objects.create_user(username="report-deactivated")
        deactivated_state = sync_user_deactivation_state(deactivated_user)
        deactivated_state.deactivated_at = now - timedelta(days=1)
        deactivated_state.permission_policy_applied = PERMISSION_POLICY_REVOKE
        deactivated_state.save(
            update_fields=["deactivated_at", "permission_policy_applied"]
        )
        deactivated_user.is_active = False
        deactivated_user.save(update_fields=["is_active"])
        old_deactivated_user = User.objects.create_user(
            username="report-old-deactivated"
        )
        old_deactivated_state = sync_user_deactivation_state(old_deactivated_user)
        old_deactivated_state.deactivation_scheduled_at = now - timedelta(days=40)
        old_deactivated_state.deactivated_at = now - timedelta(days=31)
        old_deactivated_state.permission_policy_applied = PERMISSION_POLICY_REVOKE
        old_deactivated_state.save(
            update_fields=[
                "deactivation_scheduled_at",
                "deactivated_at",
                "permission_policy_applied",
            ]
        )
        old_deactivated_user.is_active = False
        old_deactivated_user.save(update_fields=["is_active"])
        reactivated_user = User.objects.create_user(username="report-reactivated")
        reactivated_state = sync_user_deactivation_state(reactivated_user)
        reactivated_state.deactivated_at = now - timedelta(days=2)
        reactivated_state.reactivated_at = now - timedelta(days=1)
        reactivated_state.permission_policy_applied = PERMISSION_POLICY_REVOKE
        reactivated_state.deactivation_scheduled_at = now + timedelta(days=60)
        reactivated_state.save(
            update_fields=[
                "deactivated_at",
                "reactivated_at",
                "permission_policy_applied",
                "deactivation_scheduled_at",
            ]
        )

        rows = get_deactivation_report_rows(window_days=30, when=now)
        rows_by_key = {
            (row.state.user.username, row.cohort): row
            for row in rows
            if row.state.user.username.startswith("report-")
        }

        warning_row = rows_by_key[
            ("report-warning", DEACTIVATION_REPORT_COHORT_DUE_WARNING)
        ]
        self.assertEqual(warning_row.next_action, DEACTIVATION_ACTION_SEND_WARNING)
        self.assertEqual(warning_row.warning_offsets, (30, 7))
        self.assertEqual(
            warning_row.as_dict()["computed_last_activity"], warning_activity
        )
        self.assertEqual(warning_row.as_dict()["display_name"], "Report Warning")
        self.assertEqual(
            rows_by_key[
                ("report-warned", DEACTIVATION_REPORT_COHORT_ALREADY_WARNED)
            ].next_action,
            DEACTIVATION_ACTION_SEND_WARNING,
        )
        self.assertEqual(
            rows_by_key[
                ("report-staff", DEACTIVATION_REPORT_COHORT_SKIPPED)
            ].exclusion_reason,
            DEACTIVATION_EXCLUSION_STAFF,
        )
        self.assertEqual(
            get_deactivation_exclusion_reason(staff_user),
            DEACTIVATION_EXCLUSION_STAFF,
        )
        self.assertEqual(
            rows_by_key[
                (
                    "report-deactivated",
                    DEACTIVATION_REPORT_COHORT_RECENTLY_DEACTIVATED,
                )
            ].dry_run_action_summary,
            "already deactivated",
        )
        self.assertNotIn(
            ("report-old-deactivated", DEACTIVATION_REPORT_COHORT_SKIPPED),
            rows_by_key,
        )
        self.assertIn(
            (
                "report-reactivated",
                DEACTIVATION_REPORT_COHORT_RECENTLY_REACTIVATED,
            ),
            rows_by_key,
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
        anonymous_user, _ = User.objects.get_or_create(
            username=settings.ANONYMOUS_DEFAULT_USERNAME
        )
        org_creator = User.objects.create_user(username="org-creator")
        org_profile = self._create_organization(
            "org-account", "Org Account", org_creator
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
                anonymous_user,
                org_profile.user,
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
        self.assertNotIn(states[settings.ANONYMOUS_DEFAULT_USERNAME].pk, due_state_ids)
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

    @override_settings(DEACTIVATION_PERMISSION_POLICY="revoke")
    @patch(
        "onadata.apps.main.models.user_deactivation.PERMISSION_SNAPSHOT_BATCH_SIZE",
        1,
    )
    def test_snapshot_revocable_user_permissions_records_project_and_form_access(self):
        now = timezone.now()
        inactive_user = User.objects.create_user(username="snapshot-user")
        owner_creator = User.objects.create_user(username="snapshot-owner")
        owner_profile = self._create_organization(
            "snapshot-owner-org", "Snapshot Owner Org", owner_creator
        )
        owner = owner_profile.user
        shared_project = tools.create_organization_project(
            owner, "shared-project", owner_creator
        )
        owned_project = get_user_default_project(inactive_user)
        user_created_project = tools.create_organization_project(
            owner, "user-created-project", owner_creator
        )
        user_created_project.created_by = inactive_user
        user_created_project.save(update_fields=["created_by"])

        shared_xform = self._publish_test_form(
            owner, shared_project, "shared_form", owner_creator
        )
        owned_xform = self._publish_test_form(
            inactive_user, owned_project, "owned_form", inactive_user
        )
        legacy_owned_xform = self._publish_test_form(
            inactive_user, shared_project, "legacy_owned_form"
        )
        project_owned_xform = self._publish_test_form(
            owner, owned_project, "project_owned_form", owner_creator
        )
        project_created_xform = self._publish_test_form(
            owner, user_created_project, "project_created_form", owner_creator
        )

        self._clear_user_object_permissions(
            inactive_user,
            shared_project,
            owned_project,
            user_created_project,
            shared_xform,
            owned_xform,
            legacy_owned_xform,
            project_owned_xform,
            project_created_xform,
        )

        assign_perm("view_project", inactive_user, shared_project)
        assign_perm("change_project", inactive_user, owned_project)
        assign_perm("delete_project", inactive_user, owned_project)
        assign_perm("view_xform", inactive_user, shared_xform)
        assign_perm("change_xform", inactive_user, owned_xform)
        assign_perm("delete_xform", inactive_user, legacy_owned_xform)
        assign_perm("delete_xform", inactive_user, project_owned_xform)
        assign_perm("delete_xform", inactive_user, project_created_xform)

        state = sync_user_deactivation_state(inactive_user)
        stored_count = snapshot_revocable_user_permissions(
            state, when=now, run_id="snapshot-test"
        )
        duplicate_count = snapshot_revocable_user_permissions(
            state, when=now, run_id="snapshot-test"
        )

        self.assertEqual(stored_count, 4)
        self.assertEqual(duplicate_count, 0)
        snapshots = UserDeactivationPermissionSnapshot.objects.filter(
            state=state
        ).order_by("permission_codename")
        self.assertEqual(snapshots.count(), 4)

        project_snapshots = snapshots.filter(
            permission_storage_model="logger.ProjectUserObjectPermission"
        )
        xform_snapshots = snapshots.filter(
            permission_storage_model="logger.XFormUserObjectPermission"
        )
        self.assertEqual(
            set(project_snapshots.values_list("object_id", flat=True)),
            {shared_project.pk},
        )
        self.assertEqual(
            set(xform_snapshots.values_list("object_id", flat=True)),
            {shared_xform.pk, legacy_owned_xform.pk, project_created_xform.pk},
        )

        project_snapshot = project_snapshots.get(permission_codename="view_project")
        self.assertEqual(
            project_snapshot.permission_storage_model,
            "logger.ProjectUserObjectPermission",
        )
        self.assertEqual(project_snapshot.object_id, shared_project.pk)
        self.assertEqual(project_snapshot.source_organization_id, owner.pk)
        self.assertEqual(project_snapshot.source_project_id, shared_project.pk)
        self.assertIsNone(project_snapshot.source_form_id)
        self.assertEqual(project_snapshot.removed_at, now)
        self.assertEqual(project_snapshot.deactivation_run_id, "snapshot-test")

        xform_snapshot = xform_snapshots.get(permission_codename="view_xform")
        self.assertEqual(
            xform_snapshot.permission_storage_model,
            "logger.XFormUserObjectPermission",
        )
        self.assertEqual(xform_snapshot.object_id, shared_xform.pk)
        self.assertEqual(xform_snapshot.source_organization_id, owner.pk)
        self.assertEqual(xform_snapshot.source_project_id, shared_project.pk)
        self.assertEqual(xform_snapshot.source_form_id, shared_xform.pk)

    @override_settings(DEACTIVATION_PERMISSION_POLICY="revoke")
    def test_snapshot_revocable_user_permissions_revokes_org_assets_created_by_non_owner(
        self,
    ):
        inactive_user = User.objects.create_user(username="snapshot-form-creator")
        org_creator = User.objects.create_user(username="snapshot-form-org-creator")
        organization = self._create_organization(
            "snapshot-form-org", "Snapshot Form Org", org_creator
        )
        project = tools.create_organization_project(
            organization.user, "non-owner-created-project", org_creator
        )
        project.created_by = inactive_user
        project.save(update_fields=["created_by"])
        xform = self._publish_test_form(
            organization.user,
            project,
            "non_owner_created_form",
            inactive_user,
        )
        assign_perm("view_project", inactive_user, project)
        assign_perm("view_xform", inactive_user, xform)

        state = sync_user_deactivation_state(inactive_user)

        self.assertEqual(snapshot_revocable_user_permissions(state), 2)
        self.assertSetEqual(
            {
                (snapshot.permission_storage_model, snapshot.object_id)
                for snapshot in UserDeactivationPermissionSnapshot.objects.filter(
                    state=state
                )
            },
            {
                ("logger.ProjectUserObjectPermission", project.pk),
                ("logger.XFormUserObjectPermission", xform.pk),
            },
        )

    @override_settings(DEACTIVATION_PERMISSION_POLICY="revoke")
    def test_snapshot_revocable_user_permissions_skips_org_creator_and_owner(self):
        inactive_user = User.objects.create_user(username="snapshot-org-user")
        creator = User.objects.create_user(username="snapshot-org-creator")
        project_creator = User.objects.create_user(username="snapshot-project-creator")
        creator_org = self._create_organization(
            "creator-org", "Creator Org", inactive_user
        )
        owner_org = self._create_organization("owner-org", "Owner Org", creator)
        created_by_org = self._create_organization(
            "created-by-org", "Created By Org", creator
        )
        created_by_org.created_by = inactive_user
        created_by_org.save(update_fields=["created_by"])
        owner_team = get_or_create_organization_owners_team(owner_org)
        owner_team.user_set.add(inactive_user)
        creator_project = tools.create_organization_project(
            creator_org.user, "creator-org-project", inactive_user
        )
        creator_project.created_by = project_creator
        creator_project.save(update_fields=["created_by"])
        owner_project = tools.create_organization_project(
            owner_org.user, "owner-org-project", inactive_user
        )
        owner_project.created_by = project_creator
        owner_project.save(update_fields=["created_by"])
        created_by_project = tools.create_organization_project(
            created_by_org.user, "created-by-org-project", creator
        )
        created_by_project.created_by = project_creator
        created_by_project.save(update_fields=["created_by"])
        creator_xform = self._publish_test_form(
            creator_org.user, creator_project, "creator_org_form", project_creator
        )
        owner_xform = self._publish_test_form(
            owner_org.user, owner_project, "owner_org_form", project_creator
        )
        created_by_xform = self._publish_test_form(
            created_by_org.user,
            created_by_project,
            "created_by_org_form",
            project_creator,
        )

        assign_perm("view_project", inactive_user, creator_project)
        assign_perm("view_project", inactive_user, owner_project)
        assign_perm("view_project", inactive_user, created_by_project)
        assign_perm("view_xform", inactive_user, creator_xform)
        assign_perm("view_xform", inactive_user, owner_xform)
        assign_perm("view_xform", inactive_user, created_by_xform)

        state = sync_user_deactivation_state(inactive_user)

        self.assertEqual(snapshot_revocable_user_permissions(state), 0)
        self.assertFalse(
            UserDeactivationPermissionSnapshot.objects.filter(state=state).exists()
        )

    @override_settings(DEACTIVATION_PERMISSION_POLICY="preserve")
    def test_snapshot_revocable_user_permissions_ignores_preserve_policy(self):
        inactive_user = User.objects.create_user(username="snapshot-preserve-user")
        owner_creator = User.objects.create_user(username="snapshot-preserve-owner")
        owner_profile = self._create_organization(
            "snapshot-preserve-owner-org",
            "Snapshot Preserve Owner Org",
            owner_creator,
        )
        shared_project = tools.create_organization_project(
            owner_profile.user, "preserve-project", owner_creator
        )
        assign_perm("view_project", inactive_user, shared_project)
        state = sync_user_deactivation_state(inactive_user)

        self.assertEqual(snapshot_revocable_user_permissions(state), 0)
        self.assertFalse(
            UserDeactivationPermissionSnapshot.objects.filter(state=state).exists()
        )

    def test_sync_user_deactivation_state_ignores_non_users(self):
        count_before = UserDeactivationState.objects.count()

        self.assertIsNone(sync_user_deactivation_state(None))
        self.assertEqual(UserDeactivationState.objects.count(), count_before)
