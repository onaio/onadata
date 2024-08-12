# pylint: disable=import-error,ungrouped-imports
"""Module for logger tasks"""
import logging

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.db import DatabaseError

from onadata.apps.logger.models import Entity, EntityList, Project
from onadata.celeryapp import app
from onadata.libs.utils.cache_tools import PROJECT_DATE_MODIFIED_CACHE, safe_delete
from onadata.libs.utils.project_utils import set_project_perms_to_object
from onadata.libs.utils.logger_tools import soft_delete_entities_bulk


logger = logging.getLogger(__name__)
User = get_user_model()


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
def delete_entities_bulk_async(entity_pks: list[int], username: str | None = None):
    """Delete Entities asynchronously

    Args:
        entity_pks (list(int)): Primary keys of Entities to be deleted
        username (str): Username of the user initiating the delete
    """
    entity_qs = Entity.objects.filter(pk__in=entity_pks, deleted_at__isnull=True)
    deleted_by = None

    try:
        if username is not None:
            deleted_by = User.objects.get(username=username)

    except User.DoesNotExist as exc:
        logger.exception(exc)

    else:
        soft_delete_entities_bulk(entity_qs, deleted_by)
