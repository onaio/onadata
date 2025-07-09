# -*- coding: utf-8 -*-
"""
Model utility functions.
"""

import logging
from datetime import datetime
from typing import Type

from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Model
from django.utils import timezone

from onadata.libs.utils.cache_tools import safe_delete, set_cache_with_lock
from onadata.libs.utils.common_tools import get_uuid, report_exception

logger = logging.getLogger(__name__)

# pylint: disable=too-many-arguments


def set_uuid(obj):
    """
    Only give an object a new UUID if it does not have one.
    """
    if not obj.uuid:
        obj.uuid = get_uuid()


def queryset_iterator(queryset, chunksize=100):
    """
    Iterate over a Django Queryset.

    This method loads a maximum of chunksize (default: 100) rows in
    its memory at the same time while django normally would load all
    rows in its memory. Using the iterator() method only causes it to
    not preload all the classes.

    See https://docs.djangoproject.com/en/2.1/ref/models/querysets/#iterator
    """

    return queryset.iterator(chunk_size=chunksize)


def get_columns_with_hxl(survey_elements):
    """
    Returns a dictionary whose keys are xform field names and values are
    `instance::hxl` values set on the xform
    :param include_hxl - boolean value
    :param survey_elements - survey elements of an xform
    return dictionary or None
    """
    return survey_elements and {
        se.name: se.instance["hxl"]
        for se in survey_elements
        if hasattr(se, "instance") and getattr(se, "instance") and "hxl" in se.instance
    }


def update_fields_directly(instance, **fields):
    """
    Update field(s) on a model instance using QuerySet.update()
    to avoid calling save() and triggering signals.
    """
    if not fields:
        raise ValueError("At least one field must be provided to update.")

    instance.__class__.objects.filter(pk=instance.pk).update(**fields)


def adjust_numeric_field(
    model: Type[Model], pk: int, field_name: str, delta: int
) -> None:
    """Generic helper to increment a numeric field on a model instance.

    :param model: The Django model class
    :param pk: Primary key of the instance
    :param field_name: Name of the field to increment
    :param delta: Value to increment by (use negative to decrement)
    """
    # Using Queryset.update ensures we do not call the model's save method and
    # signals
    model.objects.filter(pk=pk).update(**{field_name: F(field_name) + delta})


def commit_cached_counters(
    *,
    model: Type[Model],
    field_name: str,
    key_prefix: str,
    tracked_ids_key: str,
    lock_key: str,
    created_at_key: str,
    lock_ttl: int = 7200,  # 2 hours
) -> None:
    """Commit cached counters to the database for a given model and field.

    Commit is skipped if another process holds the lock.

    :param model: The Django model class
    :param field_name: The name of the numeric field to adjust
    :param key_prefix: Cache key prefix for per-instance counters
    :param tracked_ids_key: Cache key storing modified PKs
    :param lock_key: Cache key used for locking
    :param created_at_key: Cache key for the start time of caching
    :param lock_ttl: How long to hold the lock (seconds)
    """
    lock_acquired = cache.add(lock_key, "true", timeout=lock_ttl)

    if not lock_acquired:
        return  # Another process is handling it

    instance_pks: set[int] = cache.get(tracked_ids_key, set())

    for pk in instance_pks:
        counter_key = f"{key_prefix}{pk}"
        counter = cache.get(counter_key, 0)

        if counter:
            adjust_numeric_field(model, pk=pk, field_name=field_name, delta=counter)

        safe_delete(counter_key)

    safe_delete(tracked_ids_key)
    safe_delete(lock_key)
    safe_delete(created_at_key)


def _execute_cached_counter_commit_failover(
    *,
    model: Type[Model],
    field_name: str,
    key_prefix: str,
    tracked_ids_key: str,
    lock_key: str,
    created_at_key: str,
    failover_report_key: str,
    task_name: str,
) -> None:
    """Trigger failover commit of cached counters to DB if threshold exceeded.

    :param model: Django model class
    :param field_name: Field being incremented
    :param key_prefix: Prefix for counter keys
    :param tracked_ids_key: Cache key for dirty PKs
    :param lock_key: Cache lock key
    :param created_at_key: Cache key storing start time of caching
    :param failover_report_key: Cache key to suppress duplicate alerts
    :param task_name: Name of the periodic task expected to do this commit
    """
    cache_created_at: datetime | None = cache.get(created_at_key)
    if cache_created_at is None:
        return

    failover_timeout = getattr(settings, "COUNTER_COMMIT_FAILOVER_TIMEOUT", 7200)
    time_lapse = timezone.now() - cache_created_at

    if time_lapse.total_seconds() > failover_timeout:
        commit_cached_counters(
            model=model,
            field_name=field_name,
            key_prefix=key_prefix,
            tracked_ids_key=tracked_ids_key,
            lock_key=lock_key,
            created_at_key=created_at_key,
        )

        if cache.get(failover_report_key) is None:
            subject = "Periodic task not running"
            msg = (
                f"The failover has been executed because task {task_name} "
                "is not configured or has malfunctioned"
            )
            report_exception(subject, msg)
            cache.set(failover_report_key, "sent", timeout=86400)  # throttle for 24h


def _increment_cached_counter(
    *,
    pk: int,
    key_prefix: str,
    tracked_ids_key: str,
    created_at_key: str,
    delta: int = 1,
) -> None:
    """Increment a cached numeric counter for a given object.

    :param pk: Primary key of the object
    :param key_prefix: Prefix used to generate the counter cache key
    :param delta: Value to increment by
    :param tracked_ids_key: Cache key to track which objects were modified
    :param created_at_key: Cache key to track when caching began
    """
    counter_key = f"{key_prefix}{pk}"
    created = cache.add(counter_key, 1, timeout=None)

    def add_to_modified_ids(current_ids: set | None):
        current_ids = current_ids or set()
        current_ids.add(pk)
        return current_ids

    set_cache_with_lock(
        cache_key=tracked_ids_key,
        modify_callback=add_to_modified_ids,
        cache_timeout=None,
    )
    cache.add(created_at_key, timezone.now(), timeout=None)

    if not created:
        cache.incr(counter_key, delta=delta)


def _decrement_cached_counter(
    *,
    pk: int,
    key_prefix: str,
    delta: int = 1,
) -> None:
    """Decrement a cached numeric counter for a given object, if it exists.

    :param pk: Primary key of the object
    :param key_prefix: Prefix used to generate the counter cache key
    """
    counter_key = f"{key_prefix}{pk}"

    if cache.get(counter_key) is not None:
        cache.decr(counter_key, delta=delta)


def adjust_counter(
    *,
    pk: int,
    model: Type[Model],
    field_name: str,
    delta: int,
    key_prefix: str,
    tracked_ids_key: str,
    created_at_key: str,
    lock_key: str,
    failover_report_key: str,
    task_name: str,
) -> None:
    """Adjust a numeric counter (increment or decrement) for a model instance.

    Uses cached counter if available and valid. Falls back to DB otherwise.

    :param pk: Primary key of the instance
    :param model: The Django model class
    :param field_name: The numeric field to adjust
    :param delta: Value to increment or decrement by
    :param key_prefix: Prefix used to form the cache counter key
    :param tracked_ids_key: Cache key to track modified PKs
    :param created_at_key: Cache key when caching began
    :param lock_key: Cache key used for locking
    :param failover_report_key: Cache key to throttle failover alerts
    :param task_name: Task responsible for committing to DB
    """

    def fallback_to_db():
        adjust_numeric_field(model, pk=pk, field_name=field_name, delta=delta)

    counter_key = f"{key_prefix}{pk}"

    # Always fallback to DB if cache is locked or (for decrement) counter is missing
    if cache.get(lock_key) or (delta < 0 and cache.get(counter_key) is None):
        fallback_to_db()
        return

    try:
        if delta > 0:
            _increment_cached_counter(
                pk=pk,
                key_prefix=key_prefix,
                tracked_ids_key=tracked_ids_key,
                created_at_key=created_at_key,
                delta=delta,
            )
        else:
            _decrement_cached_counter(
                pk=pk,
                key_prefix=key_prefix,
                delta=delta * -1,
            )

        _execute_cached_counter_commit_failover(
            model=model,
            field_name=field_name,
            key_prefix=key_prefix,
            tracked_ids_key=tracked_ids_key,
            lock_key=lock_key,
            created_at_key=created_at_key,
            failover_report_key=failover_report_key,
            task_name=task_name,
        )
    except ConnectionError as exc:
        logger.exception(exc)
        fallback_to_db()
