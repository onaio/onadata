from django.core.cache import cache


def safe_delete(key):
    cache.get(key) and cache.delete(key)

# Cache names used in project serializer
PROJ_PERM_CACHE = 'ps-project_permissions-'
PROJ_NUM_DATASET_CACHE = 'ps-num_datasets-'
PROJ_SUB_DATE_CACHE = 'ps-last_submission_date-'
PROJ_FORMS_CACHE = 'ps-project_forms-'

# Cache names used in user_profile_serializer
IS_ORG = 'ups-is_org-'

# Cache names user in xform_serializer
XFORM_PERMISSIONS_CACHE = 'xfs-get_xform_permissions'
ENKETO_URL_CACHE = 'xfs-get_enketo_url'
ENKETO_PREVIEW_URL_CACHE = 'xfs-get_enketo_preview_url'
XFORM_METADATA_CACHE = 'xfs-get_xform_metadata'
XFORM_DATA_VERSIONS = 'xfs-get_xform_data_versions'
DATAVIEW_COUNT = 'dvs-get_data_count'
PROJ_TEAM_USERS_CACHE = 'ps-project-team-users'
XFORM_LINKED_DATAVIEWS = 'xfs-linked_dataviews'
