# -*- coding: utf-8 -*-
"""
User deactivation lifecycle state.
"""

from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import F, Q
from django.db.models.signals import post_save
from django.utils import timezone

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.models.team import Team
from onadata.apps.logger.models.project import ProjectUserObjectPermission
from onadata.apps.logger.models.xform import XFormUserObjectPermission
from onadata.apps.main.models.user_activity import (
    UserActivity,
    get_initial_last_activity,
)

User = get_user_model()

PERMISSION_POLICY_PRESERVE = "preserve"
PERMISSION_POLICY_REVOKE = "revoke"
PERMISSION_POLICY_CHOICES = (
    ("", "Not applied"),
    (PERMISSION_POLICY_REVOKE, "Revoke"),
    (PERMISSION_POLICY_PRESERVE, "Preserve"),
)

DEACTIVATION_ACTION_SEND_WARNING = "send_warning"
DEACTIVATION_ACTION_DEACTIVATE = "deactivate"
DEACTIVATION_ACTION_NONE = "none"

DEACTIVATION_REPORT_COHORT_DUE_WARNING = "due_for_warning"
DEACTIVATION_REPORT_COHORT_DUE_DEACTIVATION = "due_for_deactivation"
DEACTIVATION_REPORT_COHORT_ALREADY_WARNED = "already_warned"
DEACTIVATION_REPORT_COHORT_SKIPPED = "skipped"
DEACTIVATION_REPORT_COHORT_RECENTLY_DEACTIVATED = "recently_deactivated"
DEACTIVATION_REPORT_COHORT_RECENTLY_REACTIVATED = "recently_reactivated"

DEACTIVATION_EXCLUSION_INACTIVE = "inactive"
DEACTIVATION_EXCLUSION_STAFF = "staff"
DEACTIVATION_EXCLUSION_SUPERUSER = "superuser"
DEACTIVATION_EXCLUSION_ORGANIZATION = "organization"
DEACTIVATION_EXCLUSION_USER_ID = "excluded_user_id"
DEACTIVATION_EXCLUSION_USERNAME = "excluded_username"

DEFAULT_DEACTIVATION_INACTIVITY_DAYS = 365
DEFAULT_DEACTIVATION_WARNING_DAYS = (30, 7)
DEFAULT_DEACTIVATION_PERMISSION_POLICY = PERMISSION_POLICY_REVOKE
DEFAULT_DEACTIVATION_REPORT_WINDOW_DAYS = 30
PERMISSION_SNAPSHOT_BATCH_SIZE = 1000

DEACTIVATION_REPORT_COLUMNS = (
    "username",
    "email",
    "display_name",
    "last_login",
    "computed_last_activity",
    "deactivation_scheduled_at",
    "warnings_sent",
    "cohort",
    "next_action",
    "next_action_date",
    "exclusion_reason",
    "permission_policy",
    "dry_run_action_summary",
)


class UserDeactivationState(models.Model):
    """
    Persisted warning/deactivation lifecycle state for a user.
    """

    user = models.OneToOneField(
        User, related_name="deactivation_state", on_delete=models.CASCADE
    )
    deactivation_scheduled_at = models.DateTimeField(
        null=True, blank=True, db_index=True
    )
    first_warning_sent_at = models.DateTimeField(null=True, blank=True)
    warned_offsets = models.JSONField(default=list, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reactivated_at = models.DateTimeField(null=True, blank=True)
    permissions_revoked_at = models.DateTimeField(null=True, blank=True)
    permission_policy_applied = models.CharField(
        max_length=20, choices=PERMISSION_POLICY_CHOICES, blank=True, default=""
    )
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "main"
        verbose_name = "user deactivation state"
        verbose_name_plural = "user deactivation states"

    def __str__(self):
        return f"{self.user.username}: {self.deactivation_scheduled_at}"

    def clear_warning_state(self, save=True):
        """
        Clear warning state for a newly computed deactivation schedule.
        """
        self.first_warning_sent_at = None
        self.warned_offsets = []

        if save:
            self.save(
                update_fields=[
                    "first_warning_sent_at",
                    "warned_offsets",
                    "date_modified",
                ]
            )

    def mark_warning_sent(self, offset_days, when=None):
        """
        Record that a warning offset has been sent.
        """
        when = when or timezone.now()
        offset_days = int(offset_days)
        warned_offsets = normalize_warning_days(
            [*(self.warned_offsets or []), offset_days]
        )

        if self.first_warning_sent_at is None:
            self.first_warning_sent_at = when
        self.warned_offsets = list(warned_offsets)
        self.save(
            update_fields=[
                "first_warning_sent_at",
                "warned_offsets",
                "date_modified",
            ]
        )


class UserDeactivationPermissionSnapshot(models.Model):
    """
    Audit snapshot of a direct object permission removed during deactivation.
    """

    state = models.ForeignKey(
        UserDeactivationState,
        related_name="permission_snapshots",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User,
        related_name="deactivation_permission_snapshots",
        on_delete=models.CASCADE,
    )
    permission_storage_model = models.CharField(max_length=128)
    permission_record_id = models.PositiveIntegerField()
    permission_codename = models.CharField(max_length=100)
    permission_name = models.CharField(max_length=255, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    object_repr = models.CharField(max_length=255, blank=True)
    source_organization_id = models.PositiveIntegerField(
        null=True, blank=True, db_index=True
    )
    source_project_id = models.PositiveIntegerField(
        null=True, blank=True, db_index=True
    )
    source_form_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    deactivation_run_id = models.CharField(max_length=64, blank=True, default="")
    removed_at = models.DateTimeField(db_index=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "main"
        verbose_name = "user deactivation permission snapshot"
        verbose_name_plural = "user deactivation permission snapshots"
        indexes = [
            models.Index(fields=["state", "deactivation_run_id"]),
            models.Index(fields=["user", "removed_at"]),
            models.Index(fields=["content_type", "object_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "state",
                    "permission_storage_model",
                    "permission_record_id",
                    "deactivation_run_id",
                ],
                name="unique_user_deact_perm_snapshot",
            )
        ]

    def __str__(self):
        return (
            f"{self.user.username}: {self.permission_codename} "
            f"on {self.object_repr or self.object_id}"
        )


@dataclass(frozen=True)
class UserDeactivationActionPlan:
    """A non-mutating action that the deactivation runner should perform."""

    state: UserDeactivationState
    action: str
    when: object
    warning_offsets: tuple = ()
    permission_policy: str = ""

    @property
    def user(self):
        """Return the user for this planned action."""
        return self.state.user

    @property
    def dry_run_action_summary(self):
        """Return a concise dry-run summary for reporting."""
        return get_deactivation_action_summary(
            self.action,
            warning_offsets=self.warning_offsets,
            permission_policy=self.permission_policy,
        )

    def as_report_row(self):
        """Return this action plan as a report row."""
        cohort = DEACTIVATION_REPORT_COHORT_DUE_WARNING
        if self.action == DEACTIVATION_ACTION_DEACTIVATE:
            cohort = DEACTIVATION_REPORT_COHORT_DUE_DEACTIVATION

        return UserDeactivationReportRow(
            state=self.state,
            cohort=cohort,
            next_action=self.action,
            next_action_date=self.when,
            warning_offsets=self.warning_offsets,
            permission_policy=self.permission_policy,
            dry_run_action_summary=self.dry_run_action_summary,
        )


@dataclass(frozen=True)
class UserDeactivationReportRow:
    """A normalized row for inactive-account reports."""

    state: UserDeactivationState
    cohort: str
    next_action: str = DEACTIVATION_ACTION_NONE
    next_action_date: object = None
    warning_offsets: tuple = ()
    exclusion_reason: str = ""
    permission_policy: str = ""
    dry_run_action_summary: str = ""

    def as_dict(self):
        """Return a dictionary ready for CSV writing."""
        user = self.state.user
        return {
            "username": user.username,
            "email": user.email,
            "display_name": user.get_full_name(),
            "last_login": user.last_login,
            "computed_last_activity": get_user_activity_at(user),
            "deactivation_scheduled_at": self.state.deactivation_scheduled_at,
            "warnings_sent": format_warning_offsets(self.state.warned_offsets),
            "cohort": self.cohort,
            "next_action": self.next_action,
            "next_action_date": self.next_action_date,
            "exclusion_reason": self.exclusion_reason,
            "permission_policy": self.permission_policy,
            "dry_run_action_summary": self.dry_run_action_summary,
        }


def get_deactivation_inactivity_days():
    """
    Return the configured inactivity threshold in days.
    """
    value = getattr(
        settings,
        "DEACTIVATION_INACTIVITY_DAYS",
        DEFAULT_DEACTIVATION_INACTIVITY_DAYS,
    )
    days = int(value)
    if days <= 0:
        raise ValueError("DEACTIVATION_INACTIVITY_DAYS must be greater than zero")
    return days


def normalize_warning_days(offsets):
    """
    Return unique positive warning offsets sorted from largest to smallest.
    """
    warning_days = {int(offset) for offset in offsets if int(offset) > 0}
    return tuple(sorted(warning_days, reverse=True))


def get_deactivation_warning_days():
    """
    Return the configured warning offsets in days.
    """
    offsets = getattr(
        settings,
        "DEACTIVATION_WARNING_DAYS",
        DEFAULT_DEACTIVATION_WARNING_DAYS,
    )
    return normalize_warning_days(offsets)


def get_deactivation_excluded_user_ids():
    """
    Return configured user ids excluded from inactive account deactivation.
    """
    return tuple(
        int(user_id)
        for user_id in getattr(settings, "DEACTIVATION_EXCLUDED_USER_IDS", [])
    )


def get_deactivation_excluded_usernames():
    """
    Return configured usernames excluded from inactive account deactivation.
    """
    usernames = {
        getattr(settings, "ANONYMOUS_DEFAULT_USERNAME", ""),
        *getattr(settings, "DEACTIVATION_EXCLUDED_USERNAMES", []),
    }
    return tuple(username for username in usernames if username)


def get_deactivation_permission_policy():
    """
    Return the configured permission policy for deactivation.
    """
    policy = getattr(
        settings,
        "DEACTIVATION_PERMISSION_POLICY",
        DEFAULT_DEACTIVATION_PERMISSION_POLICY,
    )
    if policy not in {PERMISSION_POLICY_PRESERVE, PERMISSION_POLICY_REVOKE}:
        raise ValueError(
            "DEACTIVATION_PERMISSION_POLICY must be 'preserve' or 'revoke'"
        )
    return policy


def get_user_activity_at(user):
    """
    Return the user's tracked activity timestamp, if an activity row exists.
    """
    try:
        return user.activity.last_activity
    except UserActivity.DoesNotExist:
        return None


def format_warning_offsets(offsets):
    """
    Return warning offsets as a stable comma-separated string.
    """
    return ",".join(str(offset) for offset in normalize_warning_days(offsets or []))


def get_deactivation_exclusion_reason(user):
    """
    Return why a user is excluded from automatic deactivation, or an empty string.
    """
    if user is None or not getattr(user, "pk", None):
        return ""

    if not user.is_active:
        return DEACTIVATION_EXCLUSION_INACTIVE
    if user.is_staff:
        return DEACTIVATION_EXCLUSION_STAFF
    if user.is_superuser:
        return DEACTIVATION_EXCLUSION_SUPERUSER
    if OrganizationProfile.objects.filter(user=user).exists():
        return DEACTIVATION_EXCLUSION_ORGANIZATION
    if user.pk in get_deactivation_excluded_user_ids():
        return DEACTIVATION_EXCLUSION_USER_ID
    if user.username in get_deactivation_excluded_usernames():
        return DEACTIVATION_EXCLUSION_USERNAME

    return ""


def get_deactivation_action_summary(action, warning_offsets=(), permission_policy=None):
    """
    Return a dry-run summary for a planned deactivation lifecycle action.
    """
    permission_policy = permission_policy or get_deactivation_permission_policy()

    if action == DEACTIVATION_ACTION_SEND_WARNING:
        warning_label = format_warning_labels(warning_offsets)
        return f"would send {warning_label} warning email"

    if action == DEACTIVATION_ACTION_DEACTIVATE:
        summary = "would deactivate user and revoke tokens"
        if permission_policy == PERMISSION_POLICY_REVOKE:
            return (
                f"{summary}; would snapshot and revoke eligible direct "
                "project/form permissions"
            )
        return f"{summary}; would preserve direct project/form permissions"

    return "no action"


def format_warning_labels(offsets):
    """
    Return warning offsets as human-readable day labels.
    """
    labels = [f"{offset}-day" for offset in normalize_warning_days(offsets or [])]
    if not labels:
        return "configured"
    if len(labels) == 1:
        return labels[0]
    return f"{', '.join(labels[:-1])} and {labels[-1]}"


def get_permission_revocation_protected_organization_ids(user):
    """
    Return organization user ids where the user is creator, created_by, or owner.
    """
    if user is None or not getattr(user, "pk", None):
        return set()

    creator_org_ids = OrganizationProfile.objects.filter(
        Q(creator=user) | Q(created_by=user)
    ).values_list("user_id", flat=True)
    owner_org_ids = Team.objects.filter(
        pk__in=user.groups.values("pk"),
        name__endswith=f"#{Team.OWNER_TEAM_NAME}",
    ).values_list("organization_id", flat=True)

    return {*creator_org_ids, *owner_org_ids}


def get_deactivation_scheduled_at(
    last_activity, inactivity_days=None, apply_warning_grace=False, when=None
):
    """
    Return the deactivation date for a last activity timestamp.
    """
    inactivity_days = inactivity_days or get_deactivation_inactivity_days()
    scheduled_at = last_activity + timedelta(days=inactivity_days)

    if apply_warning_grace:
        when = when or timezone.now()
        warning_days = get_deactivation_warning_days()
        if warning_days and scheduled_at <= when:
            return when + timedelta(days=warning_days[0])

    return scheduled_at


def get_revocable_user_permission_rows(user):
    """
    Yield direct project/form permission rows eligible for revoke-mode cleanup.
    """
    if user is None or not getattr(user, "pk", None):
        return

    protected_org_ids = get_permission_revocation_protected_organization_ids(user)
    project_permissions = (
        ProjectUserObjectPermission.objects.filter(user=user)
        .exclude(content_object__organization=user)
        .select_related(
            "content_object",
            "content_object__organization",
            "permission",
        )
    )
    xform_permissions = (
        XFormUserObjectPermission.objects.filter(user=user)
        .exclude(content_object__project__organization=user)
        .select_related(
            "content_object",
            "content_object__project",
            "content_object__project__organization",
            "permission",
        )
    )

    if protected_org_ids:
        project_permissions = project_permissions.exclude(
            content_object__organization_id__in=protected_org_ids
        )
        xform_permissions = xform_permissions.exclude(
            Q(content_object__project__organization_id__in=protected_org_ids)
            | Q(content_object__user_id__in=protected_org_ids)
        )

    yield from project_permissions.iterator(chunk_size=1000)
    yield from xform_permissions.iterator(chunk_size=1000)


def snapshot_revocable_user_permissions(state, when=None, run_id=""):
    """
    Store audit snapshots for direct permissions that revoke-mode will remove.
    """
    if (
        state is None
        or not getattr(state, "pk", None)
        or get_deactivation_permission_policy() != PERMISSION_POLICY_REVOKE
    ):
        return 0

    when = when or timezone.now()
    run_id = run_id or ""
    user = state.user
    permission_batch = []
    stored_count = 0
    for permission_row in get_revocable_user_permission_rows(user):
        permission_batch.append(permission_row)
        if len(permission_batch) >= PERMISSION_SNAPSHOT_BATCH_SIZE:
            stored_count += _snapshot_permission_batch(
                state=state,
                permission_rows=permission_batch,
                removed_at=when,
                run_id=run_id,
            )
            permission_batch = []

    if permission_batch:
        stored_count += _snapshot_permission_batch(
            state=state,
            permission_rows=permission_batch,
            removed_at=when,
            run_id=run_id,
        )

    return stored_count


def _snapshot_permission_batch(state, permission_rows, removed_at, run_id):
    existing_keys = set(
        UserDeactivationPermissionSnapshot.objects.filter(
            state=state,
            deactivation_run_id=run_id,
            permission_storage_model__in={
                permission_row._meta.label for permission_row in permission_rows
            },
            permission_record_id__in=[
                permission_row.pk for permission_row in permission_rows
            ],
        ).values_list("permission_storage_model", "permission_record_id")
    )
    snapshots = []
    for permission_row in permission_rows:
        key = (permission_row._meta.label, permission_row.pk)
        if key in existing_keys:
            continue

        snapshots.append(
            _build_permission_snapshot(
                state=state,
                permission_row=permission_row,
                removed_at=removed_at,
                run_id=run_id,
            )
        )

    if snapshots:
        UserDeactivationPermissionSnapshot.objects.bulk_create(
            snapshots,
            batch_size=PERMISSION_SNAPSHOT_BATCH_SIZE,
            ignore_conflicts=True,
        )

    return len(snapshots)


def _build_permission_snapshot(state, permission_row, removed_at, run_id):
    content_object = permission_row.content_object
    source_ids = _get_permission_snapshot_source_ids(permission_row)

    return UserDeactivationPermissionSnapshot(
        state=state,
        user=state.user,
        permission_storage_model=permission_row._meta.label,
        permission_record_id=permission_row.pk,
        permission_codename=permission_row.permission.codename,
        permission_name=permission_row.permission.name,
        content_type=ContentType.objects.get_for_model(content_object),
        object_id=content_object.pk,
        object_repr=str(content_object)[:255],
        source_organization_id=source_ids["organization_id"],
        source_project_id=source_ids["project_id"],
        source_form_id=source_ids["form_id"],
        deactivation_run_id=run_id,
        removed_at=removed_at,
    )


def _get_permission_snapshot_source_ids(permission_row):
    content_object = permission_row.content_object

    if permission_row._meta.model_name == "projectuserobjectpermission":
        return {
            "organization_id": content_object.organization_id,
            "project_id": content_object.pk,
            "form_id": None,
        }

    return {
        "organization_id": content_object.project.organization_id,
        "project_id": content_object.project_id,
        "form_id": content_object.pk,
    }


def get_or_create_user_activity(user):
    """
    Return a user's activity row, seeding it from historical activity if missing.
    """
    try:
        return UserActivity.objects.get(user=user)
    except UserActivity.DoesNotExist:
        return UserActivity.objects.create(
            user=user, last_activity=get_initial_last_activity(user)
        )


def sync_user_deactivation_state(user, inactivity_days=None):
    """
    Ensure lifecycle state reflects the user's current last activity.
    """
    if user is None or not getattr(user, "pk", None):
        return None

    activity = get_or_create_user_activity(user)
    scheduled_at = get_deactivation_scheduled_at(
        activity.last_activity,
        inactivity_days=inactivity_days,
        apply_warning_grace=True,
    )
    state, created = UserDeactivationState.objects.get_or_create(
        user=user, defaults={"deactivation_scheduled_at": scheduled_at}
    )

    if created or state.deactivation_scheduled_at == scheduled_at:
        return state

    state.deactivation_scheduled_at = scheduled_at
    state.clear_warning_state(save=False)
    state.save(
        update_fields=[
            "deactivation_scheduled_at",
            "first_warning_sent_at",
            "warned_offsets",
            "date_modified",
        ]
    )
    return state


def get_active_deactivation_states():
    """
    Return active users' lifecycle states that have not already been deactivated.
    """
    queryset = UserDeactivationState.objects.select_related(
        "user", "user__activity"
    ).filter(
        Q(deactivated_at__isnull=True) | Q(reactivated_at__gt=F("deactivated_at")),
        user__is_active=True,
        user__is_staff=False,
        user__is_superuser=False,
        user__profile__organizationprofile__isnull=True,
        deactivation_scheduled_at__isnull=False,
    )

    excluded_user_ids = get_deactivation_excluded_user_ids()
    if excluded_user_ids:
        queryset = queryset.exclude(user_id__in=excluded_user_ids)

    excluded_usernames = get_deactivation_excluded_usernames()
    if excluded_usernames:
        queryset = queryset.exclude(user__username__in=excluded_usernames)

    return queryset


def get_deactivation_states_due_for_warning(offset_days, when=None):
    """
    Return states whose scheduled deactivation is due for a warning offset.
    """
    when = when or timezone.now()
    offset_days = int(offset_days)
    warning_cutoff = when + timedelta(days=offset_days)

    return (
        get_active_deactivation_states()
        .filter(
            deactivation_scheduled_at__gt=when,
            deactivation_scheduled_at__lte=warning_cutoff,
        )
        .exclude(warned_offsets__contains=[offset_days])
    )


def get_deactivation_states_due_for_deactivation(when=None):
    """
    Return states whose users are due for deactivation.
    """
    when = when or timezone.now()
    queryset = get_active_deactivation_states().filter(
        deactivation_scheduled_at__lte=when
    )
    warning_days = get_deactivation_warning_days()
    if not warning_days:
        return queryset

    required_warning_days = warning_days[0]
    return queryset.filter(
        first_warning_sent_at__lte=when - timedelta(days=required_warning_days),
        warned_offsets__contains=[required_warning_days],
    )


def get_pending_deactivation_actions(when=None):
    """
    Return non-mutating warning/deactivation actions due at ``when``.
    """
    when = when or timezone.now()
    permission_policy = get_deactivation_permission_policy()
    actions_by_state_id = OrderedDict()

    for state in get_deactivation_states_due_for_deactivation(when=when).order_by(
        "deactivation_scheduled_at", "user_id"
    ):
        actions_by_state_id[state.pk] = UserDeactivationActionPlan(
            state=state,
            action=DEACTIVATION_ACTION_DEACTIVATE,
            when=when,
            permission_policy=permission_policy,
        )

    deactivation_state_ids = tuple(actions_by_state_id.keys())
    for offset_days in get_deactivation_warning_days():
        warning_queryset = get_deactivation_states_due_for_warning(
            offset_days, when=when
        ).order_by("deactivation_scheduled_at", "user_id")

        if deactivation_state_ids:
            warning_queryset = warning_queryset.exclude(pk__in=deactivation_state_ids)

        for state in warning_queryset:
            action = actions_by_state_id.get(state.pk)
            if action is None:
                actions_by_state_id[state.pk] = UserDeactivationActionPlan(
                    state=state,
                    action=DEACTIVATION_ACTION_SEND_WARNING,
                    when=when,
                    warning_offsets=(offset_days,),
                    permission_policy=permission_policy,
                )
            else:
                warning_offsets = normalize_warning_days(
                    [*action.warning_offsets, offset_days]
                )
                actions_by_state_id[state.pk] = replace(
                    action, warning_offsets=warning_offsets
                )

    return tuple(actions_by_state_id.values())


def get_next_deactivation_action(state, when=None):
    """
    Return the next expected action/date/offsets for a lifecycle state.
    """
    when = when or timezone.now()
    if (
        state is None
        or state.deactivation_scheduled_at is None
        or get_deactivation_exclusion_reason(state.user)
    ):
        return DEACTIVATION_ACTION_NONE, None, ()

    warning_days = get_deactivation_warning_days()
    warned_offsets = {int(offset) for offset in state.warned_offsets or []}
    for offset_days in warning_days:
        if offset_days in warned_offsets:
            continue

        warning_at = state.deactivation_scheduled_at - timedelta(days=offset_days)
        return (
            DEACTIVATION_ACTION_SEND_WARNING,
            max(warning_at, when),
            (offset_days,),
        )

    deactivation_at = state.deactivation_scheduled_at
    if warning_days and state.first_warning_sent_at:
        deactivation_at = max(
            deactivation_at,
            state.first_warning_sent_at + timedelta(days=warning_days[0]),
        )

    return (
        DEACTIVATION_ACTION_DEACTIVATE,
        max(deactivation_at, when),
        (),
    )


def get_deactivation_report_rows(window_days=None, when=None):
    """
    Return normalized report rows for inactive-account lifecycle cohorts.
    """
    when = when or timezone.now()
    window_days = (
        DEFAULT_DEACTIVATION_REPORT_WINDOW_DAYS
        if window_days is None
        else int(window_days)
    )
    if window_days <= 0:
        raise ValueError("window_days must be greater than zero")

    permission_policy = get_deactivation_permission_policy()
    rows = []
    seen_state_ids = set()

    for action in get_pending_deactivation_actions(when=when):
        row = action.as_report_row()
        rows.append(row)
        seen_state_ids.add(row.state.pk)

    window_start = when - timedelta(days=window_days)
    window_end = when + timedelta(days=window_days)
    rows.extend(
        _get_already_warned_report_rows(
            when=when,
            window_end=window_end,
            seen_state_ids=seen_state_ids,
            permission_policy=permission_policy,
        )
    )
    rows.extend(
        _get_recent_lifecycle_report_rows(
            when=when,
            window_start=window_start,
            seen_state_ids=seen_state_ids,
            permission_policy=permission_policy,
        )
    )
    rows.extend(
        _get_skipped_report_rows(
            window_end=window_end,
            seen_state_ids=seen_state_ids,
            permission_policy=permission_policy,
        )
    )

    return tuple(rows)


def _get_already_warned_report_rows(
    when, window_end, seen_state_ids, permission_policy
):
    rows = []
    queryset = (
        get_active_deactivation_states()
        .filter(
            deactivation_scheduled_at__gt=when,
            deactivation_scheduled_at__lte=window_end,
            first_warning_sent_at__isnull=False,
        )
        .exclude(pk__in=seen_state_ids)
        .order_by("deactivation_scheduled_at", "user_id")
    )
    for state in queryset:
        action, action_date, warning_offsets = get_next_deactivation_action(
            state, when=when
        )
        row = UserDeactivationReportRow(
            state=state,
            cohort=DEACTIVATION_REPORT_COHORT_ALREADY_WARNED,
            next_action=action,
            next_action_date=action_date,
            warning_offsets=warning_offsets,
            permission_policy=permission_policy,
            dry_run_action_summary=get_deactivation_action_summary(
                action,
                warning_offsets=warning_offsets,
                permission_policy=permission_policy,
            ),
        )
        rows.append(row)
        seen_state_ids.add(state.pk)

    return rows


def _get_recent_lifecycle_report_rows(
    when, window_start, seen_state_ids, permission_policy
):
    rows = []
    recent_deactivated = (
        UserDeactivationState.objects.select_related("user", "user__activity")
        .filter(deactivated_at__gte=window_start, deactivated_at__lte=when)
        .filter(
            Q(reactivated_at__isnull=True) | Q(reactivated_at__lte=F("deactivated_at"))
        )
        .exclude(pk__in=seen_state_ids)
        .order_by("-deactivated_at", "user_id")
    )
    for state in recent_deactivated:
        rows.append(
            UserDeactivationReportRow(
                state=state,
                cohort=DEACTIVATION_REPORT_COHORT_RECENTLY_DEACTIVATED,
                permission_policy=state.permission_policy_applied or permission_policy,
                dry_run_action_summary="already deactivated",
            )
        )
        seen_state_ids.add(state.pk)

    recent_reactivated = (
        UserDeactivationState.objects.select_related("user", "user__activity")
        .filter(reactivated_at__gte=window_start, reactivated_at__lte=when)
        .exclude(pk__in=seen_state_ids)
        .order_by("-reactivated_at", "user_id")
    )
    for state in recent_reactivated:
        rows.append(
            UserDeactivationReportRow(
                state=state,
                cohort=DEACTIVATION_REPORT_COHORT_RECENTLY_REACTIVATED,
                permission_policy=state.permission_policy_applied or permission_policy,
                dry_run_action_summary="already reactivated",
            )
        )
        seen_state_ids.add(state.pk)

    return rows


def _get_skipped_report_rows(window_end, seen_state_ids, permission_policy):
    rows = []
    skipped_queryset = (
        UserDeactivationState.objects.select_related("user", "user__activity")
        .filter(
            Q(deactivated_at__isnull=True) | Q(reactivated_at__gt=F("deactivated_at")),
            deactivation_scheduled_at__isnull=False,
            deactivation_scheduled_at__lte=window_end,
        )
        .exclude(pk__in=seen_state_ids)
        .order_by("deactivation_scheduled_at", "user_id")
    )

    for state in skipped_queryset:
        exclusion_reason = get_deactivation_exclusion_reason(state.user)
        if not exclusion_reason:
            continue

        rows.append(
            UserDeactivationReportRow(
                state=state,
                cohort=DEACTIVATION_REPORT_COHORT_SKIPPED,
                exclusion_reason=exclusion_reason,
                permission_policy=permission_policy,
                dry_run_action_summary=f"skipped: {exclusion_reason}",
            )
        )
        seen_state_ids.add(state.pk)

    return rows


# pylint: disable=unused-argument
def sync_deactivation_state_from_activity(sender, instance=None, **kwargs):
    """
    Keep lifecycle state in sync when tracked activity is created or advances.
    """
    if instance is None or not getattr(instance, "user_id", None):
        return

    sync_user_deactivation_state(instance.user)


post_save.connect(
    sync_deactivation_state_from_activity,
    sender=UserActivity,
    dispatch_uid="sync_deactivation_state_from_activity",
)
