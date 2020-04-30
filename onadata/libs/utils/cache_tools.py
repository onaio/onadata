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

# Cache names used in the open_data viewet
TABLEAU_COLUMN_HEADERS = "tableau_column_headers"
METADATA_FIELDS = [
    '_review_comment',
    '_review_status',
    '_status',
    '_edited',
    '_version',
    '_duration',
    '_notes',
    '_uuid',
    '_tags',
    '_bamboo_dataset_id',
    '_attachments',
    '_geolocation',
    '_media_count',
    '_total_media',
    '_submitted_by',
    'meta_instanceID',
    'meta/instanceID',
    '_media_all_received',
    '_xform_id_string',
    '_submission_time',
    '_xform_id']


# cache login attempts
LOCKOUT_USER = "lockout_user-"
LOGIN_ATTEMPTS = "login_attempts-"
LOCKOUT_CHANGE_PASSWORD_USER = 'lockout_change_password_user-'
CHANGE_PASSWORD_ATTEMPTS = 'change_password_attempts-'


def safe_delete(key):
    """Safely deletes a given key from the cache."""
    _ = cache.get(key) and cache.delete(key)


def safe_key(key):
    """Return a hashed key."""
    return hashlib.sha256(force_bytes(key)).hexdigest()
