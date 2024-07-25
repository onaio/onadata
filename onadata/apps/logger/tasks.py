# pylint: disable=import-error,ungrouped-imports
"""Module for logger tasks"""
import logging

from django.core.cache import cache
from django.db import DatabaseError

from onadata.apps.logger.models import EntityList, Project
from onadata.celeryapp import app
from onadata.libs.utils.cache_tools import (
    ENTITY_LIST_NUM_ENTITIES_CACHE,
    ENTITY_LIST_NUM_ENTITIES_CACHE_IDS,
    LOCK_SUFFIX,
    PROJECT_DATE_MODIFIED_CACHE,
    safe_delete,
)
from onadata.libs.utils.project_utils import set_project_perms_to_object
from onadata.libs.utils.logger_tools import inc_entity_list_num_entities_db


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
def commit_entity_list_num_entities():
    """Commit cached EntityList entities count to the database"""
    # Lock cache from further updates
    lock_key = f"{ENTITY_LIST_NUM_ENTITIES_CACHE_IDS}{LOCK_SUFFIX}"
    cache.set(lock_key, "true", 7200)
    entity_list_ids: set[int] = cache.get(ENTITY_LIST_NUM_ENTITIES_CACHE_IDS, set())

    for id in entity_list_ids:
        counter_key = f"{ENTITY_LIST_NUM_ENTITIES_CACHE}{id}"
        counter: int = cache.get(counter_key, 0)

        if counter:
            inc_entity_list_num_entities_db(id, counter)

        safe_delete(counter_key)

    safe_delete(ENTITY_LIST_NUM_ENTITIES_CACHE_IDS)
    safe_delete(lock_key)
