# -*- coding: utf-8 -*-
"""
User deactivation lifecycle state.
"""

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

DEFAULT_DEACTIVATION_INACTIVITY_DAYS = 365
DEFAULT_DEACTIVATION_WARNING_DAYS = (30, 7)
DEFAULT_DEACTIVATION_PERMISSION_POLICY = PERMISSION_POLICY_REVOKE
PERMISSION_SNAPSHOT_BATCH_SIZE = 1000


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
    queryset = UserDeactivationState.objects.select_related("user").filter(
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
