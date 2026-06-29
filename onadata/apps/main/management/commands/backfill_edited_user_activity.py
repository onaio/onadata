# -*- coding: utf-8 -*-
"""
Backfill user activity from edited submissions.
"""

from dataclasses import dataclass

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

    editor_users_seen: int = 0
    activities_created: int = 0
    activities_updated: int = 0
    states_created: int = 0
    states_updated: int = 0

    def add(self, other):
        """Add another stats object to this one."""
        self.editor_users_seen += other.editor_users_seen
        self.activities_created += other.activities_created
        self.activities_updated += other.activities_updated
        self.states_created += other.states_created
        self.states_updated += other.states_updated


def get_editor_user_id_batch(after_user_id, batch_size):
    """
    Return the next ordered batch of users who edited submissions.
    """
    return list(
        Instance.objects.filter(
            last_edited_by_id__isnull=False,
            last_edited__isnull=False,
            last_edited_by_id__gt=after_user_id,
        )
        .order_by("last_edited_by_id")
        .values_list("last_edited_by_id", flat=True)
        .distinct()[:batch_size]
    )


def get_latest_edit_times(user_ids):
    """
    Return the latest edit timestamp for each user id in the batch.
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


def process_editor_user_batch(user_ids, dry_run=False, when=None):
    """
    Backfill activity and deactivation state for one editor user-id batch.
    """
    when = when or timezone.now()
    latest_edit_times = get_latest_edit_times(user_ids)
    editor_user_ids = latest_edit_times.keys()
    activities_by_user_id = UserActivity.objects.filter(
        user_id__in=editor_user_ids
    ).in_bulk(field_name="user_id")
    states_by_user_id = UserDeactivationState.objects.filter(
        user_id__in=editor_user_ids
    ).in_bulk(field_name="user_id")
    stats = BackfillStats(editor_users_seen=len(latest_edit_times))
    activities_to_create = []
    activities_to_update = []
    states_to_create = []
    states_to_update = []

    for user_id, edit_time in latest_edit_times.items():
        activity = activities_by_user_id.get(user_id)
        activity_changed = False
        if activity is None:
            effective_activity = edit_time
            activity_changed = True
            activities_to_create.append(
                UserActivity(
                    user_id=user_id,
                    last_activity=edit_time,
                    date_created=when,
                    date_modified=when,
                )
            )
        else:
            effective_activity = max(activity.last_activity, edit_time)
            if activity.last_activity < edit_time:
                activity_changed = True
                activity.last_activity = edit_time
                activity.date_modified = when
                activities_to_update.append(activity)

        state = states_by_user_id.get(user_id)
        if state is None or activity_changed:
            scheduled_at = get_deactivation_scheduled_at(
                effective_activity,
                apply_warning_grace=True,
                when=when,
            )

        if state is None:
            states_to_create.append(
                UserDeactivationState(
                    user_id=user_id,
                    deactivation_scheduled_at=scheduled_at,
                    date_created=when,
                    date_modified=when,
                )
            )
        elif activity_changed and state.deactivation_scheduled_at != scheduled_at:
            state.deactivation_scheduled_at = scheduled_at
            state.first_warning_sent_at = None
            state.warned_offsets = []
            state.date_modified = when
            states_to_update.append(state)

    stats.activities_created = len(activities_to_create)
    stats.activities_updated = len(activities_to_update)
    stats.states_created = len(states_to_create)
    stats.states_updated = len(states_to_update)

    if dry_run:
        return stats

    UserActivity.objects.bulk_create(
        activities_to_create,
        batch_size=len(activities_to_create) or None,
        ignore_conflicts=True,
    )
    UserActivity.objects.bulk_update(
        activities_to_update,
        fields=["last_activity", "date_modified"],
        batch_size=len(activities_to_update) or None,
    )
    UserDeactivationState.objects.bulk_create(
        states_to_create,
        batch_size=len(states_to_create) or None,
        ignore_conflicts=True,
    )
    UserDeactivationState.objects.bulk_update(
        states_to_update,
        fields=[
            "deactivation_scheduled_at",
            "first_warning_sent_at",
            "warned_offsets",
            "date_modified",
        ],
        batch_size=len(states_to_update) or None,
    )

    return stats


def backfill_edited_user_activity(
    batch_size=DEFAULT_BATCH_SIZE,
    start_after_user_id=0,
    max_users=None,
    dry_run=False,
    stdout=None,
    verbosity=1,
):
    """
    Backfill edited-submission activity in bounded batches.
    """
    total_stats = BackfillStats()
    after_user_id = start_after_user_id

    while True:
        next_batch_size = batch_size
        if max_users is not None:
            remaining = max_users - total_stats.editor_users_seen
            if remaining <= 0:
                break
            next_batch_size = min(next_batch_size, remaining)

        user_ids = get_editor_user_id_batch(after_user_id, next_batch_size)
        if not user_ids:
            break

        if dry_run:
            batch_stats = process_editor_user_batch(user_ids, dry_run=True)
        else:
            with transaction.atomic():
                batch_stats = process_editor_user_batch(user_ids)

        total_stats.add(batch_stats)
        after_user_id = user_ids[-1]

        if stdout is not None and verbosity > 1:
            stdout.write(
                "Processed editor users through "
                f"user id {after_user_id}: {batch_stats.editor_users_seen}"
            )

    return total_stats


class Command(BaseCommand):
    """Backfill user activity from edited submissions."""

    help = gettext_lazy(
        "Backfill UserActivity and UserDeactivationState from edited submissions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=gettext_lazy(
                "Number of distinct editor user ids to process per batch."
            ),
        )
        parser.add_argument(
            "--start-after-user-id",
            type=int,
            default=0,
            help=gettext_lazy("Resume after this editor user id."),
        )
        parser.add_argument(
            "--max-users",
            type=int,
            help=gettext_lazy("Maximum distinct editor users to process."),
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

        stats = backfill_edited_user_activity(
            batch_size=batch_size,
            start_after_user_id=start_after_user_id,
            max_users=max_users,
            dry_run=options["dry_run"],
            stdout=self.stdout,
            verbosity=options["verbosity"],
        )
        if options["verbosity"] > 0:
            action = "Would process" if options["dry_run"] else "Processed"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action} {stats.editor_users_seen} editor users; "
                    f"activities created={stats.activities_created}, "
                    f"activities updated={stats.activities_updated}, "
                    f"states created={stats.states_created}, "
                    f"states updated={stats.states_updated}."
                )
            )
