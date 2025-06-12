"""
Asynchronous tasks for the logger app
"""

import logging

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import DatabaseError, OperationalError

from multidb.pinning import use_master

from onadata.apps.logger.models import Entity, EntityList, Instance, Project, XForm
from onadata.apps.logger.models.instance import (
    save_full_json,
    update_project_date_modified,
    update_xform_submission_count,
)
from onadata.celeryapp import app
from onadata.libs.kms.tools import (
    adjust_xform_decrypted_submission_count,
    commit_cached_xform_decrypted_submission_count,
    decrypt_instance,
    disable_expired_keys,
    rotate_expired_keys,
    send_key_rotation_reminder,
)
from onadata.libs.permissions import set_project_perms_to_object
from onadata.libs.utils.cache_tools import PROJECT_DATE_MODIFIED_CACHE, safe_delete
from onadata.libs.utils.entities_utils import (
    adjust_elist_num_entities,
    commit_cached_elist_num_entities,
    soft_delete_entities_bulk,
)
from onadata.libs.utils.logger_tools import (
    reconstruct_xform_export_register,
    register_instance_repeat_columns,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# pylint: disable=too-few-public-methods
class AutoRetryTask(app.Task):
    """Base task class for retrying exceptions"""

    retry_backoff = 3
    autoretry_for = (DatabaseError, ConnectionError, OperationalError)


@app.task(base=AutoRetryTask)
@use_master
def set_entity_list_perms_async(entity_list_id):
    """Set permissions for EntityList asynchronously

    :param entity_list_id: Primary key for EntityList
    """
    try:
        entity_list = EntityList.objects.get(pk=entity_list_id)

    except EntityList.DoesNotExist as err:
        logger.exception(err)
        return

    set_project_perms_to_object(entity_list, entity_list.project)


@app.task(base=AutoRetryTask)
@use_master
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


@app.task(base=AutoRetryTask)
@use_master
def delete_entities_bulk_async(entity_pks: list[int], username: str | None = None):
    """Delete Entities asynchronously

    :param entity_pks: Primary keys of Entities to be deleted
    :param username: Username of the user initiating the delete operation
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


@app.task(base=AutoRetryTask)
@use_master
def commit_cached_elist_num_entities_async():
    """Commit cached EntityList `num_entities` counter to the database

    Call this task periodically, such as in a background task to ensure
    cached counters for EntityList `num_entities` are commited to the
    database.

    Cached counters have no expiry, so it is essential to ensure that
    this task is called periodically.
    """
    commit_cached_elist_num_entities()


@app.task(base=AutoRetryTask)
@use_master
def incr_elist_num_entities_async(elist_pk: int):
    """Increment EntityList `num_entities` counter asynchronously

    :param elist_pk: Primary key for EntityList
    """
    adjust_elist_num_entities(elist_pk, delta=1)


@app.task(base=AutoRetryTask)
@use_master
def decr_elist_num_entities_async(elist_pk: int) -> None:
    """Decrement EntityList `num_entities` counter asynchronously

    :param elist_pk: Primary key for EntityList
    """
    adjust_elist_num_entities(elist_pk, delta=-1)


@app.task(base=AutoRetryTask)
@use_master
def register_instance_repeat_columns_async(instance_pk: int) -> None:
    """Register Instance repeat columns asynchronously

    :param instance_pk: Primary key for Instance
    """
    try:
        instance = Instance.objects.get(pk=instance_pk)

    except Instance.DoesNotExist as exc:
        logger.exception(exc)

    else:
        register_instance_repeat_columns(instance)


@app.task(base=AutoRetryTask)
@use_master
def reconstruct_xform_export_register_async(xform_id: int) -> None:
    """Register a XForm's Instances export columns asynchronously

    :param xform_id: Primary key for XForm
    """
    try:
        xform = XForm.objects.get(pk=xform_id)

    except XForm.DoesNotExist as exc:
        logger.exception(exc)

    else:
        reconstruct_xform_export_register(xform)


@app.task(base=AutoRetryTask)
@use_master
def update_xform_submission_count_async(instance_id):
    """Update an XForm's submission count asynchronously"""
    try:
        instance = Instance.objects.get(pk=instance_id)
    except Instance.DoesNotExist as exc:
        logger.exception(exc)
    else:
        update_xform_submission_count(instance)


@app.task(base=AutoRetryTask)
@use_master
def save_full_json_async(instance_id):
    """Save an Instance's JSON asynchronously"""
    try:
        instance = Instance.objects.get(pk=instance_id)
    except Instance.DoesNotExist as exc:
        logger.exception(exc)
    else:
        save_full_json(instance)


@app.task(base=AutoRetryTask)
@use_master
def update_project_date_modified_async(instance_id):
    """Update a Project's date_modified asynchronously"""
    try:
        instance = Instance.objects.get(pk=instance_id)

    except Instance.DoesNotExist as exc:
        logger.exception(exc)

    else:
        update_project_date_modified(instance)


@app.task(base=AutoRetryTask)
@use_master
def decrypt_instance_async(instance_id: int):
    """Decrypt encrypted Instance asynchronously.

    :param instance_id: Primary key for Instance
    """
    try:
        instance = Instance.objects.get(pk=instance_id)

    except Instance.DoesNotExist as exc:
        logger.exception(exc)

    else:
        decrypt_instance(instance)


@app.task(retry_backoff=3, autoretry_for=(DatabaseError, ConnectionError))
@use_master
def rotate_expired_keys_async():
    """Rotate expired keys asynchronously."""
    rotate_expired_keys()


@app.task(retry_backoff=3, autoretry_for=(DatabaseError, ConnectionError))
@use_master
def disable_expired_keys_async():
    """Disable expired keys asynchronously."""
    disable_expired_keys()


@app.task(retry_backoff=3, autoretry_for=(DatabaseError, ConnectionError))
@use_master
def send_key_rotation_reminder_async():
    """Send key rotation reminder asynchronously."""
    send_key_rotation_reminder()


@app.task(retry_backoff=3, autoretry_for=(DatabaseError, ConnectionError))
@use_master
def decr_xform_decrypted_submission_count_async(xform_id: int) -> None:
    """Decrement XForm decrypted submission count asynchronously

    :param xform_id: Primary key for XForm
    """
    try:
        xform = XForm.objects.get(pk=xform_id)

    except XForm.DoesNotExist as exc:
        logger.exception(exc)

    else:
        adjust_xform_decrypted_submission_count(xform, delta=-1)


@app.task(retry_backoff=3, autoretry_for=(DatabaseError, ConnectionError))
@use_master
def commit_cached_xform_decrypted_submission_count_async():
    """Commit cached XForm decrypted submission count to the database

    Call this task periodically, such as in a background task to ensure
    cached counters for XForm `num_of_decrypted_submissions` are commited
    to the database.

    Cached counters have no expiry, so it is essential to ensure that
    this task is called periodically.
    """
    commit_cached_xform_decrypted_submission_count()
