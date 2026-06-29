# -*- coding: utf-8 -*-
"""
User activity tracking.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Max
from django.db.models.signals import post_save
from django.utils import timezone

User = get_user_model()


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
        from onadata.apps.logger.models import XForm

        latest_submission_time = XForm.objects.filter(
            user=user, last_submission_time__isnull=False
        ).aggregate(last_submission_time=Max("last_submission_time"))[
            "last_submission_time"
        ]

    candidates = [
        value
        for value in (user.last_login, latest_submission_time, user.date_joined)
        if value is not None
    ]
    return max(candidates) if candidates else timezone.now()


def record_user_activity(user, when=None, force=False):
    """
    Record successful authenticated activity for a real Django user.
    """
    if user is None or not getattr(user, "pk", None):
        return None

    if not getattr(user, "is_active", True):
        return None

    when = when or timezone.now()
    activity, created = UserActivity.objects.get_or_create(
        user=user, defaults={"last_activity": when}
    )

    if created:
        return activity

    if activity.last_activity and activity.last_activity >= when:
        return activity

    min_interval = getattr(settings, "ACTIVITY_TRACKING_MIN_INTERVAL_SECONDS", 300)
    stale_before = when - timedelta(seconds=min_interval)
    should_update = (
        force
        or activity.last_activity is None
        or activity.last_activity <= stale_before
    )

    if not should_update:
        return activity

    activity.last_activity = when
    activity.save(update_fields=["last_activity", "date_modified"])
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
