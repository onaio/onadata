# -*- coding: utf-8 -*-
"""
User deactivation lifecycle state.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import F, Q
from django.db.models.signals import post_save
from django.utils import timezone

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
    return tuple(
        username
        for username in getattr(settings, "DEACTIVATION_EXCLUDED_USERNAMES", [])
        if username
    )


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
