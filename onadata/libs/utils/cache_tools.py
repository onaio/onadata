# -*- coding: utf-8 -*-
"""
Cache utilities.
"""
import hashlib

from django.core.cache import cache
from django.utils.encoding import force_bytes

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

# Cache timeouts used in XForm model
XFORM_REGENERATE_INSTANCE_JSON_TASK_TTL = 24 * 60 * 60  # 24 hrs converted to seconds


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
