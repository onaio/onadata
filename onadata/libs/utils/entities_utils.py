import logging
from datetime import datetime
from typing import Any

from django.conf import settings
from django.db.models import F, QuerySet
from django.utils import timezone

from onadata.apps.logger.models import Entity, EntityList, Instance, RegistrationForm
from onadata.apps.logger.xform_instance_parser import (
    get_entity_uuid_from_xml,
    get_meta_from_xml,
)
from onadata.libs.utils.cache_tools import (
    ELIST_FAILOVER_REPORT_SENT,
    ELIST_NUM_ENTITIES,
    ELIST_NUM_ENTITIES_CREATED_AT,
    ELIST_NUM_ENTITIES_IDS,
    ELIST_NUM_ENTITIES_LOCK,
    cache,
    safe_delete,
    set_cache_with_lock,
)
from onadata.libs.utils.common_tools import report_exception
from onadata.libs.utils.model_tools import queryset_iterator

logger = logging.getLogger(__name__)


def get_entity_json_from_instance(
    instance: Instance, registration_form: RegistrationForm
) -> dict:
    """Parses Instance json and returns Entity json

    Args:
        instance (Instance): Submission to create Entity

    Returns:
        dict: Entity properties
    """
    instance_json: dict[str, Any] = instance.get_dict()
    # Getting a mapping of save_to field to the field name
    mapped_properties = registration_form.get_save_to(instance.version)
    # Field names with an alias defined
    property_fields = list(mapped_properties.values())

    def get_field_alias(field_name: str) -> str:
        """Get the alias (save_to value) of a form field"""
        for alias, field in mapped_properties.items():
            if field == field_name:
                return alias

        return field_name

    def parse_instance_json(data: dict[str, Any]) -> None:
        """Parse the original json, replacing field names with their alias

        The data keys are modified in place
        """
        for field_name in list(data):
            field_data = data[field_name]
            del data[field_name]

            if field_name.startswith("formhub"):
                continue

            if field_name.startswith("meta"):
                if field_name == "meta/entity/label":
                    data["label"] = field_data

                continue

            # We extract field names within grouped sections
            ungrouped_field_name = field_name.split("/")[-1]

            if ungrouped_field_name in property_fields:
                field_alias = get_field_alias(ungrouped_field_name)
                data[field_alias] = field_data

    parse_instance_json(instance_json)

    return instance_json


def create_entity_from_instance(
    instance: Instance, registration_form: RegistrationForm
) -> Entity:
    """Create an Entity

    Args:
        instance (Instance): Submission from which the Entity is created from
        registration_form (RegistrationForm): RegistrationForm creating the
        Entity

    Returns:
        Entity: A newly created Entity
    """
    entity_json = get_entity_json_from_instance(instance, registration_form)
    entity_list = registration_form.entity_list
    entity = Entity.objects.create(
        entity_list=entity_list,
        json=entity_json,
        uuid=get_entity_uuid_from_xml(instance.xml),
    )
    entity.history.create(
        registration_form=registration_form,
        xml=instance.xml,
        instance=instance,
        form_version=instance.version,
        json=entity_json,
        created_by=instance.user,
    )

    return entity


def update_entity_from_instance(
    uuid: str, instance: Instance, registration_form: RegistrationForm
) -> Entity | None:
    """Updates Entity

    Args:
        uuid (str): uuid of the Entity to be updated
        instance (Instance): Submission that updates an Entity

    Returns:
        Entity | None: updated Entity if uuid valid, else None
    """
    try:
        entity = Entity.objects.get(uuid=uuid)

    except Entity.DoesNotExist as err:
        logger.exception(err)
        return None

    patch_data = get_entity_json_from_instance(instance, registration_form)
    entity.json = {**entity.json, **patch_data}
    entity.save()
    entity.history.create(
        registration_form=registration_form,
        xml=instance.xml,
        instance=instance,
        form_version=instance.version,
        json=entity.json,
        created_by=instance.user,
    )

    return entity


def soft_delete_entities_bulk(entity_qs: QuerySet[Entity], deleted_by=None) -> None:
    """Soft delete Entities in bulk

    Args:
        entity_qs QuerySet(Entity): Entity queryset
        deleted_by (User): User initiating the delete
    """
    for entity in queryset_iterator(entity_qs):
        entity.soft_delete(deleted_by)


def create_or_update_entity_from_instance(instance: Instance) -> None:
    """Create or Update Entity from Instance

    Args:
        instance (Instance): Instance to create/update Entity from
    """
    registration_form_qs = RegistrationForm.objects.filter(
        xform=instance.xform, is_active=True
    )
    entity_node = get_meta_from_xml(instance.xml, "entity")

    if not registration_form_qs.exists() or not entity_node:
        return

    registration_form = registration_form_qs.first()
    mutation_success_checks = ["1", "true"]
    entity_uuid = entity_node.getAttribute("id")
    exists = False

    if entity_uuid is not None:
        exists = Entity.objects.filter(uuid=entity_uuid).exists()

    if exists and entity_node.getAttribute("update") in mutation_success_checks:
        # Update Entity
        update_entity_from_instance(entity_uuid, instance, registration_form)

    elif not exists and entity_node.getAttribute("create") in mutation_success_checks:
        # Create Entity
        create_entity_from_instance(instance, registration_form)


def _inc_elist_num_entities_db(pk: int, count=1) -> None:
    """Increment EntityList `num_entities` counter in the database

    Args:
        pk (int): Primary key for EntityList
        count (int): Value to increase by
    """
    # Using Queryset.update ensures we do not call the model's save method and
    # signals
    EntityList.objects.filter(pk=pk).update(num_entities=F("num_entities") + count)


def _dec_elist_num_entities_db(pk: int, count=1) -> None:
    """Decrement EntityList `num_entities` counter in the database

    Args:
        pk (int): Primary key for EntityList
        count (int): Value to decrease by
    """
    # Using Queryset.update ensures we do not call the model's save method and
    # signals
    EntityList.objects.filter(pk=pk).update(num_entities=F("num_entities") - count)


def _inc_elist_num_entities_cache(pk: int) -> None:
    """Increment EntityList `num_entities` counter in cache

    Args:
        pk (int): Primary key for EntityList
    """
    counter_cache_key = f"{ELIST_NUM_ENTITIES}{pk}"
    # Cache timeout is None (no expiry). A background task should be run
    # periodically to persist the cached counters to the db
    # and delete the cache. If we were to set a timeout, the cache could
    # expire before the next periodic run and data will be lost.
    counter_cache_ttl = None
    counter_cache_created = cache.add(counter_cache_key, 1, counter_cache_ttl)

    def add_to_cached_ids(current_ids: set | None):
        if current_ids is None:
            current_ids = set()

        if pk not in current_ids:
            current_ids.add(pk)

        return current_ids

    set_cache_with_lock(ELIST_NUM_ENTITIES_IDS, add_to_cached_ids, counter_cache_ttl)
    cache.add(ELIST_NUM_ENTITIES_CREATED_AT, timezone.now(), counter_cache_ttl)

    if not counter_cache_created:
        cache.incr(counter_cache_key)


def _dec_elist_num_entities_cache(pk: int) -> None:
    """Decrement EntityList `num_entities` counter in cache

    Args:
        pk (int): Primary key for EntityList
    """
    counter_cache_key = f"{ELIST_NUM_ENTITIES}{pk}"

    if cache.get(counter_cache_key) is not None:
        cache.decr(counter_cache_key)


def inc_elist_num_entities(pk: int) -> None:
    """Increment EntityList `num_entities` counter

    Updates cached counter if cache is not locked. Else, the database
    counter is updated

    Args:
        pk (int): Primary key for EntityList
    """

    if _is_elist_num_entities_cache_locked():
        _inc_elist_num_entities_db(pk)

    else:
        try:
            _inc_elist_num_entities_cache(pk)
            _exec_cached_elist_counter_commit_failover()

        except ConnectionError as exc:
            logger.exception(exc)
            # Fallback to db if cache inacessible
            _inc_elist_num_entities_db(pk)


def dec_elist_num_entities(pk: int) -> None:
    """Decrement EntityList `num_entities` counter

    Updates cached counter if cache is not locked. Else, the database
    counter is updated.

    Args:
        pk (int): Primary key for EntityList
    """
    counter_cache_key = f"{ELIST_NUM_ENTITIES}{pk}"

    if _is_elist_num_entities_cache_locked() or cache.get(counter_cache_key) is None:
        _dec_elist_num_entities_db(pk)

    else:
        try:
            _dec_elist_num_entities_cache(pk)

        except ConnectionError as exc:
            logger.exception(exc)
            # Fallback to db if cache inacessible
            _dec_elist_num_entities_db(pk)


def _is_elist_num_entities_cache_locked() -> bool:
    """Checks if EntityList `num_entities` cached counter is locked

    Typically, the cache is locked if the cached data is in the process
    of being persisted in the database.

    The cache is locked to ensure no further updates are made when the
    data is being committed to the database.

    Returns True, if cache is locked, False otherwise
    """

    return cache.get(ELIST_NUM_ENTITIES_LOCK) is not None


def commit_cached_elist_num_entities() -> None:
    """Commit cached EntityList `num_entities` counter to the database

    Commit is successful if no other process holds the lock
    """
    lock_acquired = cache.add(ELIST_NUM_ENTITIES_LOCK, "true", 7200)

    if lock_acquired:
        entity_list_pks: set[int] = cache.get(ELIST_NUM_ENTITIES_IDS, set())

        for pk in entity_list_pks:
            counter_key = f"{ELIST_NUM_ENTITIES}{pk}"
            counter: int = cache.get(counter_key, 0)

            if counter:
                _inc_elist_num_entities_db(pk, counter)

            safe_delete(counter_key)

        safe_delete(ELIST_NUM_ENTITIES_IDS)
        safe_delete(ELIST_NUM_ENTITIES_LOCK)
        safe_delete(ELIST_NUM_ENTITIES_CREATED_AT)


def _exec_cached_elist_counter_commit_failover() -> None:
    """Check the time lapse since the cached EntityList `num_entities`
    counters were created and commit if the time lapse exceeds
    the threshold allowed.

    Acts as a failover incase the cron job responsible for committing
    the cached data fails or is not configured
    """
    cache_created_at: datetime | None = cache.get(ELIST_NUM_ENTITIES_CREATED_AT)

    if cache_created_at is None:
        return

    # If the time lapse is > ELIST_COUNTER_COMMIT_FAILOVER_TIMEOUT, run the failover
    failover_timeout: int = getattr(
        settings, "ELIST_COUNTER_COMMIT_FAILOVER_TIMEOUT", 7200
    )
    time_lapse = timezone.now() - cache_created_at

    if time_lapse.total_seconds() > failover_timeout:
        commit_cached_elist_num_entities()
        # Do not send report exception if already sent within the past 24 hrs
        if cache.get(ELIST_FAILOVER_REPORT_SENT) is None:
            subject = "Periodic task not running"
            task_name = (
                "onadata.apps.logger.tasks.commit_cached_elist_num_entities_async"
            )
            msg = (
                f"The failover has been executed because task {task_name} "
                "is not configured or has malfunctioned"
            )
            report_exception(subject, msg)
            cache.set(ELIST_FAILOVER_REPORT_SENT, "sent", 86400)
