# pylint: disable=import-error,ungrouped-imports
"""Module for logger tasks"""
import logging

from django.core.cache import cache
from django.db import DatabaseError

from onadata.apps.logger.models import EntityList, Project
from onadata.celeryapp import app
from onadata.libs.utils.cache_tools import (
    PROJECT_DATE_MODIFIED_CACHE,
    safe_delete,
)
from onadata.libs.utils.project_utils import set_project_perms_to_object
from onadata.libs.utils.logger_tools import commit_cached_elist_num_entities


logger = logging.getLogger(__name__)


@app.task(retry_backoff=3, autoretry_for=(DatabaseError, ConnectionError))
def set_entity_list_perms_async(entity_list_id):
    """Set permissions for EntityList asynchronously

    Args:
        pk (int): Primary key for EntityList
    """
    try:
        entity_list = EntityList.objects.get(pk=entity_list_id)

    except EntityList.DoesNotExist as err:
        logger.exception(err)
        return

    set_project_perms_to_object(entity_list, entity_list.project)


@app.task(retry_backoff=3, autoretry_for=(DatabaseError, ConnectionError))
def apply_project_date_modified_async():
    """
    Batch update projects date_modified field periodically
    """
    project_ids = cache.get(PROJECT_DATE_MODIFIED_CACHE, {})
    if not project_ids:
        return

    # Update project date_modified field in batches
    for project_id, timestamp in project_ids.items():
        Project.objects.filter(pk=project_id).update(date_modified=timestamp)

    # Clear cache after updating
    safe_delete(PROJECT_DATE_MODIFIED_CACHE)


@app.task(retry_backoff=3, autoretry_for=(DatabaseError, ConnectionError))
def commit_cached_elist_num_entities_async():
    """Commit cached EntityList `num_entities` counter to the database

    Call this task periodically, such as in a background task to ensure
    cached counters for EntityList `num_entities` are commited to the
    database.

    Cached counters have no expiry, so it is essential to ensure that
    this task is called periodically.
    """
    commit_cached_elist_num_entities()
