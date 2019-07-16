import re

from django.core.cache import cache

# Cache names used in project serializer
PROJ_PERM_CACHE = "ps-project_permissions-"
PROJ_NUM_DATASET_CACHE = "ps-num_datasets-"
PROJ_SUB_DATE_CACHE = "ps-last_submission_date-"
PROJ_FORMS_CACHE = "ps-project_forms-"
PROJ_BASE_FORMS_CACHE = "ps-project_base_forms-"

# Cache names used in user_profile_serializer
IS_ORG = "ups-is_org-"

# Cache names user in xform_serializer
XFORM_PERMISSIONS_CACHE = "xfs-get_xform_permissions"
ENKETO_URL_CACHE = "xfs-get_enketo_url"
ENKETO_PREVIEW_URL_CACHE = "xfs-get_enketo_preview_url"
XFORM_METADATA_CACHE = "xfs-get_xform_metadata"
XFORM_DATA_VERSIONS = "xfs-get_xform_data_versions"
XFORM_COUNT = "xfs-submission_count"
DATAVIEW_COUNT = "dvs-get_data_count"
DATAVIEW_LAST_SUBMISSION_TIME = "dvs-last_submission_time"
PROJ_TEAM_USERS_CACHE = "ps-project-team-users"
XFORM_LINKED_DATAVIEWS = "xfs-linked_dataviews"
PROJECT_LINKED_DATAVIEWS = "ps-project-linked_dataviews"

# cache login attempts
LOCKOUT_USER = "lockout_user-"
LOGIN_ATTEMPTS = "login_attempts-"


def safe_delete(key):
    cache.get(key) and cache.delete(key)


def safe_key(key):
    """Return a valid cache key"""
    valid_key_chars_re = re.compile("[\x21-\x7e\x80-\xff]+$")
    if not valid_key_chars_re.match(key):
        return safe_key(key.replace(" ", "-"))

    return key
