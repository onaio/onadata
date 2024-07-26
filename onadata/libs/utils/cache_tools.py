# -*- coding: utf-8 -*-
"""
Cache utilities.
"""
import hashlib
import logging
import socket

from collections import defaultdict
from threading import Lock

from django.core.cache import cache
from django.utils.encoding import force_bytes

logger = logging.getLogger(__name__)
# Define a global dictionary to store locks for each key
locks = defaultdict(Lock)

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

# Cache timeouts used in XForm model
XFORM_REGENERATE_INSTANCE_JSON_TASK_TTL = 24 * 60 * 60  # 24 hrs converted to seconds
XFORM_MANIFEST_CACHE_TTL = 10 * 60  # 10 minutes converted to seconds
XFORM_MANIFEST_CACHE_LOCK_TTL = 300  # 5 minutes converted to seconds

# Project date modified cache
PROJECT_DATE_MODIFIED_CACHE = "project_date_modified"

LOCK_SUFFIX = "-lock"

# Entities
ELIST_NUM_ENTITIES = "el-num-entities-"
ELIST_NUM_ENTITIES_IDS = "el-num-entities-ids"
ELIST_NUM_ENTITIES_LOCK = f"{ELIST_NUM_ENTITIES_IDS}{LOCK_SUFFIX}"
ELIST_NUM_ENTITIES_CREATED_AT = f"{ELIST_NUM_ENTITIES_IDS}-created-at"


def safe_delete(key):
    """Safely deletes a given key from the cache."""
    _ = cache.get(key) and cache.delete(key)


def safe_key(key):
    """Return a hashed key."""
    return hashlib.sha256(force_bytes(key)).hexdigest()


def reset_project_cache(project, request, project_serializer_class):
    """
    Clears and sets project cache
    """

    # Clear all project cache entries
    for prefix in project_cache_prefixes:
        safe_delete(f"{prefix}{project.pk}")

    # Reserialize project and cache value
    # Note: The ProjectSerializer sets all the other cache entries
    project_cache_data = project_serializer_class(
        project, context={"request": request}
    ).data
    cache.set(f"{PROJ_OWNER_CACHE}{project.pk}", project_cache_data)


def safe_cache_set(key, value, timeout=None):
    """
    Safely set a value in the cache.

    If the cache is not reachable, the operation silently fails.

    Args:
        key (str): The cache key to set.
        value (Any): The value to store in the cache.
        timeout (int, optional): The cache timeout in seconds. If None,
            the default cache timeout will be used.
    Returns:
        None
    """
    try:
        cache.set(key, value, timeout)
    except ConnectionError as exc:
        # Handle cache connection error
        logger.exception(exc)
    except socket.error as exc:
        # Handle other potential connection errors, especially for
        # older Python versions
        logger.exception(exc)


def safe_cache_get(key, default=None):
    """
    Safely get a value from the cache.

    If the cache is not reachable, the operation silently fails.

    Args:
        key (str): The cache key to retrieve.
        default (Any): The default value to return if the cache is inaccessible
            or the key does not exist.
    Returns:
        Any: The value from the cache if accessible, otherwise the default value.
    """
    try:
        return cache.get(key, default)
    except ConnectionError as exc:
        # Handle cache connection error
        logger.exception(exc)
        return default
    except socket.error as exc:
        # Handle other potential connection errors, especially for
        # older Python versions
        logger.exception(exc)
        return default


def get_lock_for_key(key):
    """
    Get a lock for a specific cache key.

    Args:
        key (str): The name of the cache key.

    Returns:
        Lock: The lock associated with the key.
    """
    return locks[key]


def add_to_cached_set(set_name, item, timeout=3600):
    """
    Add an item to a cached set using locking to avoid race conditions.

    Args:
        set_name (str): The name of the set.
        item (str): The item to add to the set.
    """

    lock = get_lock_for_key(set_name)

    with lock:
        cached_set = cache.get(set_name, set())

        if item not in cached_set:
            cached_set.add(item)
            cache.set(set_name, cached_set, timeout)
