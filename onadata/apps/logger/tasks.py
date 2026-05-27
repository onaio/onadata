"""Asynchronous tasks for the logger app"""

import logging

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import DatabaseError, OperationalError

from celery.exceptions import MaxRetriesExceededError
from multidb.pinning import use_master
from valigetta.exceptions import ConnectionException as ValigettaConnectionException

from onadata.apps.logger.models import Entity, EntityList, Instance, Project, XForm
from onadata.apps.logger.models.instance import (
    save_full_json,
    update_project_date_modified,
    update_xform_submission_count,
)
from onadata.apps.messaging.constants import ENTITY_LIST, ENTITY_LIST_IMPORTED
from onadata.apps.messaging.serializers import send_message
from onadata.celeryapp import app
from onadata.libs.exceptions import NotAllMediaReceivedError
from onadata.libs.kms.tools import (
    adjust_xform_num_of_decrypted_submissions,
    commit_cached_xform_num_of_decrypted_submissions,
    decrypt_instance,
    disable_expired_keys,
    rotate_expired_keys,
    save_decryption_error,
    send_key_grace_expiry_reminder,
    send_key_rotation_reminder,
)
from onadata.libs.permissions import set_project_perms_to_object
from onadata.libs.utils.cache_tools import (
    PROJECT_DATE_MODIFIED_CACHE,
    safe_cache_delete,
    safe_cache_get,
)
from onadata.libs.utils.common_tags import DECRYPTION_FAILURE_MAX_RETRIES
from onadata.libs.utils.entities_utils import (
    adjust_elist_num_entities,
    commit_cached_elist_num_entities,
    import_entities_from_csv,
    soft_delete_entities_bulk,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# pylint: disable=too-few-public-methods
class AutoRetryTask(app.Task):
    """Base task class for retrying exceptions"""

    retry_backoff = 3
    autoretry_for = (DatabaseError, ConnectionError, OperationalError)
    max_retries = 5


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
    project_ids = safe_cache_get(PROJECT_DATE_MODIFIED_CACHE, {})
    if not project_ids:
        return

    # Update project date_modified field in batches
    for project_id, timestamp in project_ids.items():
        Project.objects.filter(pk=project_id).update(date_modified=timestamp)

    # Clear cache after updating
    safe_cache_delete(PROJECT_DATE_MODIFIED_CACHE)


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
def adjust_elist_num_entities_async(elist_pk: int, delta: int):
    """Increment EntityList `num_entities` counter asynchronously

    :param elist_pk: Primary key for EntityList
    """
    try:
        entity_list = EntityList.objects.get(pk=elist_pk)

    except EntityList.DoesNotExist as exc:
        logger.exception(exc)

    else:
        adjust_elist_num_entities(entity_list, delta=delta)


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


class DecryptInstanceAutoRetryTask(AutoRetryTask):
    """Custom task class for decrypting instances with auto-retry"""

    retry_backoff = 5
    max_retries = 8
    autoretry_for = (
        *AutoRetryTask.autoretry_for,
        ValigettaConnectionException,
        NotAllMediaReceivedError,
    )

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Override `on_failure` to save decryption error if max retries exceeded"""
        instance = self.get_instance_from_args(args, kwargs)

        if instance is not None and isinstance(exc, MaxRetriesExceededError):
            save_decryption_error(instance, DECRYPTION_FAILURE_MAX_RETRIES)

        super().on_failure(exc, task_id, args, kwargs, einfo)

    def get_instance_from_args(self, args, kwargs):
        """Get Instance from args or kwargs"""
        instance_id = args[0] if args else kwargs.get("instance_id")

        if instance_id is not None:
            try:
                return Instance.objects.get(pk=instance_id)
            except Instance.DoesNotExist as exc:
                logger.exception(exc)
        return None


@app.task(base=DecryptInstanceAutoRetryTask, bind=True)
@use_master
def decrypt_instance_async(self, instance_id: int):
    """Decrypt encrypted Instance asynchronously.

    :param instance_id: Primary key for Instance
    """
    try:
        instance = Instance.objects.get(pk=instance_id)

    except Instance.DoesNotExist as exc:
        logger.exception(exc)

    else:
        decrypt_instance(instance)

        logger.info(
            "Decryption successful - XForm: %s; Instance: %s; Task: %s",
            instance.xform_id,
            instance_id,
            self.request.id,
        )


@app.task(base=AutoRetryTask)
@use_master
def rotate_expired_keys_async():
    """Rotate expired keys asynchronously."""
    rotate_expired_keys()


@app.task(base=AutoRetryTask)
@use_master
def disable_expired_keys_async():
    """Disable expired keys asynchronously."""
    disable_expired_keys()


@app.task(base=AutoRetryTask)
@use_master
def send_key_rotation_reminder_async():
    """Send key rotation reminder asynchronously."""
    send_key_rotation_reminder()


@app.task(base=AutoRetryTask)
@use_master
def adjust_xform_num_of_decrypted_submissions_async(xform_id: int, delta: int) -> None:
    """Adjust XForm `num_of_decrypted_submissions` counter asynchronously

    :param xform_id: Primary key for XForm
    :param delta: Value to increment or decrement by
    """
    try:
        xform = XForm.objects.get(pk=xform_id)

    except XForm.DoesNotExist as exc:
        logger.exception(exc)

    else:
        adjust_xform_num_of_decrypted_submissions(xform, delta=delta)


@app.task(base=AutoRetryTask)
@use_master
def commit_cached_xform_num_of_decrypted_submissions_async():
    """Commit cached XForm `num_of_decrypted_submissions` counter to the database

    Call this task periodically, such as in a background task to ensure
    cached counters for XForm `num_of_decrypted_submissions` are commited
    to the database.

    Cached counters have no expiry, so it is essential to ensure that
    this task is called periodically.
    """
    commit_cached_xform_num_of_decrypted_submissions()


@app.task(base=AutoRetryTask)
@use_master
def send_key_grace_expiry_reminder_async():
    """Send key grace expiry reminder asynchronously."""
    send_key_grace_expiry_reminder()


@app.task(base=AutoRetryTask, bind=True)
@use_master
# pylint: disable=too-many-positional-arguments, too-many-arguments
def import_entities_from_csv_async(
    self,
    file_path: str,
    entity_list_id: int,
    label_column: str = "label",
    uuid_column: str = "uuid",
    user_id: int | None = None,
):
    """Import entities from CSV asynchronously."""
    self.update_state(state="STARTED", meta={"processed": 0})
    created = updated = processed = 0
    errors: list[tuple[int, str]] = []
    entity_list = EntityList.objects.get(pk=entity_list_id)
    user = User.objects.get(pk=user_id) if user_id else None

    with default_storage.open(file_path, mode="r") as csv_file:
        for row_result in import_entities_from_csv(
            entity_list,
            csv_file,
            user=user,
            label_column=label_column,
            uuid_column=uuid_column,
        ):
            processed += 1

            if row_result.status == "created":
                created += 1

            elif row_result.status == "updated":
                updated += 1

            else:
                errors.append((row_result.index, row_result.error or "Unknown error"))

            if processed % 25 == 0:
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "processed": processed,
                        "created": created,
                        "updated": updated,
                        "errors": errors[-5:],
                    },
                )

    send_message(
        instance_id=entity_list.pk,
        target_id=entity_list.pk,
        target_type=ENTITY_LIST,
        user=user,
        message_verb=ENTITY_LIST_IMPORTED,
    )

    return {
        "processed": processed,
        "created": created,
        "updated": updated,
        "errors": errors[:50],
    }
