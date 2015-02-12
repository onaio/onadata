from django.core.cache import cache


def safe_delete(key):
    cache.get(key) and cache.delete(key)

# Cache names used in project serializers
PROJ_PERM_CACHE = 'ps-project_permissions-'
PROJ_NUM_DATASET_CACHE = 'ps-num_datasets-'
PROJ_SUB_DATE_CACHE = 'ps-last_submission_date-'
PROJ_FORMS_CACHE = 'ps-project_forms-'
