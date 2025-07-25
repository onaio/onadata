# -*- coding: utf-8 -*-
"""
Cache utilities.
"""

import hashlib
import logging
import socket
import time
from contextlib import contextmanager

from django.core.cache import cache
from django.utils.encoding import force_bytes

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = cache.default_timeout

# Cache names used in project serializer
PROJ_PERM_CACHE = "ps-project_permissions-"
PROJ_NUM_DATASET_CACHE = "ps-num_datasets-"
PROJ_SUB_DATE_CACHE = "ps-last_submission_date-"
PROJ_FORMS_CACHE = "ps-project_forms-"
PROJ_BASE_FORMS_CACHE = "ps-project_base_forms-"
PROJ_OWNER_CACHE = "ps-project_owner-"
project_cache_prefixes = [
    PROJ_PERM_CACHE,
    PROJ_NUM_DATASET_CACHE,
    PROJ_SUB_DATE_CACHE,
    PROJ_FORMS_CACHE,
    PROJ_BASE_FORMS_CACHE,
    PROJ_OWNER_CACHE,
]

# Cache names used in user_profile_serializer
IS_ORG = "ups-is_org-"
USER_PROFILE_PREFIX = "user_profile-"

# Cache names user in xform_serializer
XFORM_PERMISSIONS_CACHE = "xfs-get_xform_permissions"
ENKETO_URL_CACHE = "xfs-get_enketo_url"
ENKETO_SINGLE_SUBMIT_URL_CACHE = "xfs-get_enketosingle_submit__url"
ENKETO_PREVIEW_URL_CACHE = "xfs-get_enketo_preview_url"
XFORM_METADATA_CACHE = "xfs-get_xform_metadata"
XFORM_DATA_VERSIONS = "xfs-get_xform_data_versions"
XFORM_COUNT = "xfs-submission_count"
DATAVIEW_COUNT = "dvs-get_data_count"
DATAVIEW_LAST_SUBMISSION_TIME = "dvs-last_submission_time"
PROJ_TEAM_USERS_CACHE = "ps-project-team-users"
XFORM_LINKED_DATAVIEWS = "xfs-linked_dataviews"
PROJECT_LINKED_DATAVIEWS = "ps-project-linked_dataviews"

# Cache names used in organization profile viewset
ORG_PROFILE_CACHE = "org-profile-"

# cache login attempts
LOCKOUT_IP = "lockout_ip-"
LOGIN_ATTEMPTS = "login_attempts-"
LOCKOUT_CHANGE_PASSWORD_USER = "lockout_change_password_user-"  # noqa
CHANGE_PASSWORD_ATTEMPTS = "change_password_attempts-"  # noqa

# Cache names used in XForm Model
XFORM_SUBMISSION_COUNT_FOR_DAY = "xfm-get_submission_count-"
XFORM_SUBMISSION_COUNT_FOR_DAY_DATE = "xfm-get_submission_count_date-"
XFORM_SUBMISSION_STAT = "xfm-get_form_submissions_grouped_by_field-"
XFORM_CHARTS = "xfm-get_form_charts-"
XFORM_REGENERATE_INSTANCE_JSON_TASK = "xfm-regenerate_instance_json_task-"
XFORM_MANIFEST_CACHE = "xfm-manifest-"
XFORM_LIST_CACHE = "xfm-list-"
XFROM_LIST_CACHE_TTL = 10 * 60  # 10 minutes converted to seconds
XFORM_SUBMISSIONS_DELETING = "xfm-submissions-deleting-"
XFORM_SUBMISSIONS_DELETING_TTL = 60 * 60  # 1 hour converted to seconds
XFORM_DEC_SUBMISSION_COUNT = "xfm-dec-submission-count-"
XFORM_DEC_SUBMISSION_COUNT_IDS = "xfm-dec-submission-count-ids"
XFORM_DEC_SUBMISSION_COUNT_LOCK = f"{XFORM_DEC_SUBMISSION_COUNT_IDS}-lock"
XFORM_DEC_SUBMISSION_COUNT_CREATED_AT = f"{XFORM_DEC_SUBMISSION_COUNT_IDS}-created-at"
XFORM_DEC_SUBMISSION_COUNT_FAILOVER_REPORT_SENT = (
    "xfm-dec-submission-count-failover-report-sent"
)

# Cache timeouts used in XForm model
XFORM_REGENERATE_INSTANCE_JSON_TASK_TTL = 24 * 60 * 60  # 24 hrs converted to seconds
XFORM_MANIFEST_CACHE_TTL = 10 * 60  # 10 minutes converted to seconds
XFORM_MANIFEST_CACHE_LOCK_TTL = 300  # 5 minutes converted to seconds

# Project date modified cache
PROJECT_DATE_MODIFIED_CACHE = "project_date_modified"


# Entities
ELIST_NUM_ENTITIES = "elist-num-entities-"
ELIST_NUM_ENTITIES_IDS = "elist-num-entities-ids"
ELIST_NUM_ENTITIES_LOCK = f"{ELIST_NUM_ENTITIES_IDS}-lock"
ELIST_NUM_ENTITIES_CREATED_AT = f"{ELIST_NUM_ENTITIES_IDS}-created-at"

# Report exception
ELIST_FAILOVER_REPORT_SENT = "elist-failover-report-sent"

# KMS
KMS_TOKEN_CACHE_KEY = "kms-token"
KMS_TOKEN_CACHE_TTL = 60 * 60 * 24  # 24 hours


def safe_cache_delete(key):
    """Safely deletes a given key from the cache."""
    _safe_cache_operation(lambda: cache.delete(key))


def safe_key(key):
    """Return a hashed key."""
    return hashlib.sha256(force_bytes(key)).hexdigest()


def reset_project_cache(project, request, project_serializer_class):
    """
    Clears and sets project cache
    """

    # Clear all project cache entries
    for prefix in project_cache_prefixes:
        safe_cache_delete(f"{prefix}{project.pk}")

    # Reserialize project and cache value
    # Note: The ProjectSerializer sets all the other cache entries
    project_cache_data = project_serializer_class(
        project, context={"request": request}
    ).data
    cache.set(f"{PROJ_OWNER_CACHE}{project.pk}", project_cache_data)


def _safe_cache_operation(operation, default_return=None):
    """
    Generic wrapper for cache operations with error handling.

    Args:
        operation (callable): The cache operation to execute.
        default_return (Any): The default value to return on error.
    Returns:
        Any: The result of the operation or the default value on error.
    """
    try:
        return operation()
    except (ConnectionError, socket.error, ValueError) as exc:
        logger.exception(exc)

        return default_return


def safe_cache_set(key, value, timeout=DEFAULT_TIMEOUT):
    """
    Safely set a value in the cache.

    If the cache is not reachable, the operation silently fails.

    :param key: The cache key to set.
    :param value: The value to store in the cache.
    :param timeout: The cache timeout in seconds. If None,
        the default cache timeout will be used.
    """
    return _safe_cache_operation(lambda: cache.set(key, value, timeout))


def safe_cache_get(key, default=None):
    """
    Safely get a value from the cache.

    If the cache is not reachable, the operation silently fails.

    :param key: The cache key to get.
    :param default: The default value to return if the key is not found.
    :return: The value from the cache or the default value.
    """
    return _safe_cache_operation(lambda: cache.get(key, default), default)


def safe_cache_add(key, value, timeout=DEFAULT_TIMEOUT):
    """
    Safely add a value to the cache.

    If the cache is not reachable, the operation silently fails.

    :param key: The cache key to add.
    :param value: The value to store in the cache.
    :param timeout: The cache timeout in seconds. If None,
        the default cache timeout will be used.
    :return: True if the value was added to the cache, False otherwise.
    """
    return _safe_cache_operation(lambda: cache.add(key, value, timeout), False)


def safe_cache_incr(key, delta=1):
    """
    Safely increment a value in the cache.

    If the cache is not reachable, the operation silently fails.

    Args:
        key (str): The cache key to increment.
        delta (int): The amount to increment by (default: 1).
    Returns:
        int: The new value after incrementing, or None if the operation fails.
    """
    return _safe_cache_operation(lambda: cache.incr(key, delta))


def safe_cache_decr(key, delta=1):
    """
    Safely decrement a value in the cache.

    If the cache is not reachable, the operation silently fails.

    Args:
        key (str): The cache key to decrement.
        delta (int): The amount to decrement by (default: 1).
    Returns:
        int: The new value after decrementing, or None if the operation fails.
    """
    return _safe_cache_operation(lambda: cache.decr(key, delta))


class CacheLockError(Exception):
    """Custom exception raised when a cache lock cannot be acquired."""


@contextmanager
def with_cache_lock(cache_key, lock_expire=30, lock_timeout=10):
    """
    Context manager for safely setting a cache value with a lock.

    Args:
        cache_key (str): The key under which the value is stored in the cache.
        lock_expire (int): The expiration time for the lock in seconds.
        lock_timeout (int): The maximum time to wait for the lock in seconds.

    Raises:
        CacheLockError: If the lock cannot be acquired within
                        the specified lock_timeout.

    Yields:
        None
    """
    lock_key = f"lock:{cache_key}"
    start_time = time.time()

    # Try to acquire the lock
    lock_acquired = cache.add(lock_key, "locked", lock_expire)

    while not lock_acquired and time.time() - start_time < lock_timeout:
        time.sleep(0.1)
        lock_acquired = cache.add(lock_key, "locked", lock_expire)

    if not lock_acquired:
        raise CacheLockError(f"Could not acquire lock for {cache_key}")

    try:
        yield

    finally:
        cache.delete(lock_key)


def set_cache_with_lock(
    cache_key,
    modify_callback,
    cache_timeout=DEFAULT_TIMEOUT,
    lock_expire=30,
    lock_timeout=10,
):
    """
    Set a cache value with a lock, using a callback function to modify the value.

    Use of lock ensures that race conditions are avoided, even when multiple processes
    or threads attempt to modifiy the cache concurrently.

    :param cache_key: The key under which the value is stored in the cache.
    :param modify_callback: A callback function that takes the current cache
                            value and returns the modified value.
    :param cache_timeout: The expiration time for the cached value in seconds.
    :param lock_expire: The expiration time for the lock in seconds.
    :param lock_timeout: The maximum time to wait for the lock in seconds.

    :raises CacheLockError: If the lock cannot be acquired within the specified
                            lock_timeout.
    """
    with with_cache_lock(cache_key, lock_expire, lock_timeout):
        # Get the current value from cache
        current_value = cache.get(cache_key)
        # Use the callback to get the modified value
        new_value = modify_callback(current_value)
        # Set the new value in the cache with the specified timeout
        cache.set(cache_key, new_value, cache_timeout)
