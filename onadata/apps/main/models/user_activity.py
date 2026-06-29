# -*- coding: utf-8 -*-
"""
User activity tracking.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.cache.backends.base import InvalidCacheBackendError
from django.db import DatabaseError, models
from django.db.models import Max
from django.db.models.signals import post_save
from django.utils import timezone

from pylibmc import Error as PyLibMCError
from redis.exceptions import RedisError

from onadata.libs.utils.cache_tools import safe_cache_delete

User = get_user_model()

USER_ACTIVITY_CACHE_PREFIX = "user-activity-"
USER_ACTIVITY_CACHE_ERRORS = (
    InvalidCacheBackendError,
    PyLibMCError,
    RedisError,
    ConnectionError,
    OSError,
    TimeoutError,
)


class UserActivity(models.Model):
    """
    Persisted latest activity for a user.
    """

    user = models.OneToOneField(User, related_name="activity", on_delete=models.CASCADE)
    last_activity = models.DateTimeField(db_index=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "main"
        verbose_name = "user activity"
        verbose_name_plural = "user activity"

    def __str__(self):
        return f"{self.user.username}: {self.last_activity}"


def get_initial_last_activity(user):
    """
    Return the best available historical activity signal for a user.
    """
    latest_submission_time = None
    if getattr(user, "pk", None):
        # Import here to avoid a model import cycle during app loading.
        from onadata.apps.logger.models import Instance

        latest_submission_time = Instance.objects.filter(
            user=user, date_created__isnull=False
        ).aggregate(last_submission_time=Max("date_created"))["last_submission_time"]
        latest_edit_time = Instance.objects.filter(
            last_edited_by=user, last_edited__isnull=False
        ).aggregate(last_edit_time=Max("last_edited"))["last_edit_time"]
    else:
        latest_edit_time = None

    candidates = [
        value
        for value in (
            user.last_login,
            latest_submission_time,
            latest_edit_time,
            user.date_joined,
        )
        if value is not None
    ]
    return max(candidates) if candidates else timezone.now()


def add_user_activity_cache_key(cache_key, timeout):
    """
    Add a per-user activity cache key.
    """
    try:
        return cache.add(cache_key, True, timeout=timeout)
    except USER_ACTIVITY_CACHE_ERRORS:
        return None


def record_user_activity(user, when=None, force=False):
    """
    Record successful authenticated activity for a real Django user.
    """
    if user is None or not getattr(user, "pk", None):
        return None

    if not getattr(user, "is_active", True):
        return None

    when = when or timezone.now()
    min_interval = getattr(settings, "ACTIVITY_TRACKING_MIN_INTERVAL_SECONDS", 300)
    cache_key = f"{USER_ACTIVITY_CACHE_PREFIX}{user.pk}"
    cache_acquired = False

    if not force and min_interval > 0:
        cache_added = add_user_activity_cache_key(cache_key, min_interval)
        cache_acquired = cache_added is True
        if cache_added is False:
            return None

    try:
        activity, created = UserActivity.objects.get_or_create(
            user=user, defaults={"last_activity": when}
        )
    except DatabaseError:
        if cache_acquired:
            safe_cache_delete(cache_key)
        raise

    if created:
        return activity

    if activity.last_activity and activity.last_activity >= when:
        return activity

    stale_before = when - timedelta(seconds=min_interval)
    update_filter = {
        "pk": activity.pk,
        "last_activity__lt": when,
    }
    if not force:
        update_filter["last_activity__lte"] = stale_before

    try:
        updated = UserActivity.objects.filter(**update_filter).update(
            last_activity=when, date_modified=timezone.now()
        )
    except DatabaseError:
        if cache_acquired:
            safe_cache_delete(cache_key)
        raise

    if updated:
        activity.last_activity = when
        post_save.send(
            sender=UserActivity,
            instance=activity,
            created=False,
            raw=False,
            using=activity._state.db,
            update_fields={"last_activity", "date_modified"},
        )

    return activity


# pylint: disable=unused-argument
def create_user_activity(sender, instance=None, created=False, **kwargs):
    """
    Seed an activity row for newly created users.
    """
    if created and instance is not None:
        UserActivity.objects.get_or_create(
            user=instance,
            defaults={"last_activity": get_initial_last_activity(instance)},
        )


post_save.connect(create_user_activity, sender=User, dispatch_uid="user_activity")
