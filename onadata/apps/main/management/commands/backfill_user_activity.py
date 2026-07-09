# -*- coding: utf-8 -*-
"""
Backfill historical user activity in bounded batches.
"""

from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext_lazy

from onadata.apps.logger.models import Instance
from onadata.apps.main.models.user_activity import UserActivity
from onadata.apps.main.models.user_deactivation import (
    UserDeactivationState,
    get_deactivation_scheduled_at,
)

DEFAULT_BATCH_SIZE = 1000
MAX_BATCH_SIZE = 10000


@dataclass
class BackfillStats:
    """Counts for a backfill run or batch."""

    users_seen: int = 0
    activities_created: int = 0
    activities_updated: int = 0
    states_created: int = 0
    states_updated: int = 0

    def add(self, other):
        """Add another stats object to this one."""
        self.users_seen += other.users_seen
        self.activities_created += other.activities_created
        self.activities_updated += other.activities_updated
        self.states_created += other.states_created
        self.states_updated += other.states_updated


@dataclass
class BackfillBatchChanges:
    """Objects to write for one backfill batch."""

    stats: BackfillStats
    when: object
    activities_to_create: list = field(default_factory=list)
    activities_to_update: list = field(default_factory=list)
    states_to_create: list = field(default_factory=list)
    states_to_update: list = field(default_factory=list)

    def stage_activity(self, user_id, activity_time, activity):
        """Stage a UserActivity create/update and return the effective activity."""
        if activity is None:
            self.activities_to_create.append(
                UserActivity(
                    user_id=user_id,
                    last_activity=activity_time,
                    date_created=self.when,
                    date_modified=self.when,
                )
            )
            return activity_time, True

        if activity.last_activity < activity_time:
            activity.last_activity = activity_time
            activity.date_modified = self.when
            self.activities_to_update.append(activity)
            return activity_time, True

        return activity.last_activity, False

    def stage_deactivation_state(
        self, user_id, effective_activity, activity_changed, state
    ):
        """Stage a UserDeactivationState create/update for a computed activity."""
        scheduled_at = None
        if state is None or activity_changed:
            scheduled_at = get_deactivation_scheduled_at(
                effective_activity,
                apply_warning_grace=True,
                when=self.when,
            )

        if state is None:
            self.states_to_create.append(
                UserDeactivationState(
                    user_id=user_id,
                    deactivation_scheduled_at=scheduled_at,
                    date_created=self.when,
                    date_modified=self.when,
                )
            )
        elif activity_changed and state.deactivation_scheduled_at != scheduled_at:
            state.deactivation_scheduled_at = scheduled_at
            state.first_warning_sent_at = None
            state.warned_offsets = []
            state.date_modified = self.when
            self.states_to_update.append(state)

    def finalize_stats(self):
        """Populate stats from the accumulated write lists."""
        self.stats.activities_created = len(self.activities_to_create)
        self.stats.activities_updated = len(self.activities_to_update)
        self.stats.states_created = len(self.states_to_create)
        self.stats.states_updated = len(self.states_to_update)

    def write(self):
        """Persist accumulated backfill changes."""
        UserActivity.objects.bulk_create(
            self.activities_to_create,
            batch_size=len(self.activities_to_create) or None,
            ignore_conflicts=True,
        )
        UserActivity.objects.bulk_update(
            self.activities_to_update,
            fields=["last_activity", "date_modified"],
            batch_size=len(self.activities_to_update) or None,
        )
        UserDeactivationState.objects.bulk_create(
            self.states_to_create,
            batch_size=len(self.states_to_create) or None,
            ignore_conflicts=True,
        )
        UserDeactivationState.objects.bulk_update(
            self.states_to_update,
            fields=[
                "deactivation_scheduled_at",
                "first_warning_sent_at",
                "warned_offsets",
                "date_modified",
            ],
            batch_size=len(self.states_to_update) or None,
        )


def get_user_id_batch(after_user_id, batch_size):
    """
    Return the next ordered batch of user ids.
    """
    user_model = get_user_model()
    return list(
        user_model.objects.filter(pk__gt=after_user_id)
        .order_by("pk")
        .values_list("pk", flat=True)[:batch_size]
    )


def get_latest_submission_times(user_ids):
    """
    Return the latest submission timestamp for each submitter user id.
    """
    return dict(
        Instance.objects.filter(
            user_id__in=user_ids,
            date_created__isnull=False,
        )
        .values("user_id")
        .annotate(activity_time=Max("date_created"))
        .values_list("user_id", "activity_time")
    )


def get_latest_edit_times(user_ids):
    """
    Return the latest edit timestamp for each editor user id.
    """
    return dict(
        Instance.objects.filter(
            last_edited_by_id__in=user_ids,
            last_edited__isnull=False,
        )
        .values("last_edited_by_id")
        .annotate(activity_time=Max("last_edited"))
        .values_list("last_edited_by_id", "activity_time")
    )


def get_activity_time(user, latest_submission_times, latest_edit_times):
    """
    Return the best available historical activity timestamp for a user.
    """
    candidates = [
        value
        for value in (
            user.last_login,
            latest_submission_times.get(user.pk),
            latest_edit_times.get(user.pk),
            user.date_joined,
        )
        if value is not None
    ]
    return max(candidates) if candidates else None


def get_users_by_id(user_ids):
    """
    Return users keyed by id.
    """
    user_model = get_user_model()
    return user_model.objects.filter(pk__in=user_ids).in_bulk()


def get_existing_activity_and_state(user_ids, dry_run=False):
    """
    Return existing activity and state rows keyed by user id.
    """
    activity_queryset = UserActivity.objects.filter(user_id__in=user_ids)
    state_queryset = UserDeactivationState.objects.filter(user_id__in=user_ids)
    if not dry_run:
        activity_queryset = activity_queryset.select_for_update()
        state_queryset = state_queryset.select_for_update()

    return (
        activity_queryset.in_bulk(field_name="user_id"),
        state_queryset.in_bulk(field_name="user_id"),
    )


def process_user_batch(user_ids, dry_run=False, when=None):
    """
    Backfill activity and deactivation state for one user-id batch.
    """
    when = when or timezone.now()
    users_by_id = get_users_by_id(user_ids)
    latest_submission_times = get_latest_submission_times(user_ids)
    latest_edit_times = get_latest_edit_times(user_ids)
    activities_by_user_id, states_by_user_id = get_existing_activity_and_state(
        user_ids, dry_run=dry_run
    )
    changes = BackfillBatchChanges(
        stats=BackfillStats(users_seen=len(users_by_id)), when=when
    )

    for user_id in user_ids:
        user = users_by_id.get(user_id)
        if user is None:
            continue

        activity_time = get_activity_time(
            user,
            latest_submission_times,
            latest_edit_times,
        )
        if activity_time is None:
            continue

        effective_activity, activity_changed = changes.stage_activity(
            user_id, activity_time, activities_by_user_id.get(user_id)
        )
        changes.stage_deactivation_state(
            user_id,
            effective_activity,
            activity_changed,
            states_by_user_id.get(user_id),
        )

    changes.finalize_stats()
    if dry_run:
        return changes.stats

    changes.write()
    return changes.stats


def backfill_user_activity(
    batch_size=DEFAULT_BATCH_SIZE,
    start_after_user_id=0,
    max_users=None,
    dry_run=False,
    progress_callback=None,
):
    """
    Backfill historical user activity in bounded batches.
    """
    total_stats = BackfillStats()
    after_user_id = start_after_user_id

    while True:
        next_batch_size = batch_size
        if max_users is not None:
            remaining = max_users - total_stats.users_seen
            if remaining <= 0:
                break
            next_batch_size = min(next_batch_size, remaining)

        user_ids = get_user_id_batch(after_user_id, next_batch_size)
        if not user_ids:
            break

        if dry_run:
            batch_stats = process_user_batch(user_ids, dry_run=True)
        else:
            with transaction.atomic():
                batch_stats = process_user_batch(user_ids)

        total_stats.add(batch_stats)
        after_user_id = user_ids[-1]

        if progress_callback is not None:
            progress_callback(after_user_id, batch_stats)

    return total_stats


class Command(BaseCommand):
    """Backfill historical user activity."""

    help = gettext_lazy(
        "Backfill UserActivity and UserDeactivationState for existing users."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=gettext_lazy("Number of users to process per batch."),
        )
        parser.add_argument(
            "--start-after-user-id",
            type=int,
            default=0,
            help=gettext_lazy("Resume after this user id."),
        )
        parser.add_argument(
            "--max-users",
            type=int,
            help=gettext_lazy("Maximum users to process."),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=gettext_lazy("Report counts without writing changes."),
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        start_after_user_id = options["start_after_user_id"]
        max_users = options["max_users"]
        if batch_size < 1 or batch_size > MAX_BATCH_SIZE:
            raise CommandError(f"--batch-size must be between 1 and {MAX_BATCH_SIZE}.")
        if start_after_user_id < 0:
            raise CommandError("--start-after-user-id must be zero or greater.")
        if max_users is not None and max_users < 1:
            raise CommandError("--max-users must be greater than zero.")

        progress_callback = None
        if options["verbosity"] > 1:

            def write_progress(after_user_id, batch_stats):
                self.stdout.write(
                    "Processed users through "
                    f"user id {after_user_id}: {batch_stats.users_seen}"
                )

            progress_callback = write_progress

        stats = backfill_user_activity(
            batch_size=batch_size,
            start_after_user_id=start_after_user_id,
            max_users=max_users,
            dry_run=options["dry_run"],
            progress_callback=progress_callback,
        )
        if options["verbosity"] > 0:
            action = "Would process" if options["dry_run"] else "Processed"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action} {stats.users_seen} users; "
                    f"activities created={stats.activities_created}, "
                    f"activities updated={stats.activities_updated}, "
                    f"states created={stats.states_created}, "
                    f"states updated={stats.states_updated}."
                )
            )
