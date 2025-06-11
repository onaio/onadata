import logging
from typing import Any

from django.db.models import QuerySet

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
)
from onadata.libs.utils.model_tools import (
    adjust_counter,
    commit_cached_counters,
    queryset_iterator,
)

logger = logging.getLogger(__name__)


def get_entity_json_from_instance(
    instance: Instance, registration_form: RegistrationForm
) -> dict:
    """Parses Instance json and returns Entity json

    :param instance: Instance to create Entity from
    :param registration_form: RegistrationForm to create Entity from
    :return: Entity properties
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

    :param instance: Submission from which the Entity is created from
    :param registration_form: RegistrationForm creating the Entity
    :return: A newly created Entity
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

    :param uuid: uuid of the Entity to be updated
    :param instance: Submission that updates an Entity
    :param registration_form: RegistrationForm updating the Entity
    :return: updated Entity if uuid valid, else None
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

    :param entity_qs: Entity queryset
    :param deleted_by: User initiating the delete
    """
    for entity in queryset_iterator(entity_qs):
        entity.soft_delete(deleted_by)


def create_or_update_entity_from_instance(instance: Instance) -> None:
    """Create or Update Entity from Instance

    :param instance: Instance to create/update Entity from
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


def adjust_elist_num_entities(pk: int, incr: bool) -> None:
    """Adjust EntityList `num_entities` counter

    :param pk: Primary key for EntityList
    :param incr: True to increment, False to decrement
    """
    adjust_counter(
        pk=pk,
        model=EntityList,
        field_name="num_entities",
        incr=incr,
        key_prefix=ELIST_NUM_ENTITIES,
        tracked_ids_key=ELIST_NUM_ENTITIES_IDS,
        created_at_key=ELIST_NUM_ENTITIES_CREATED_AT,
        lock_key=ELIST_NUM_ENTITIES_LOCK,
        failover_report_key=ELIST_FAILOVER_REPORT_SENT,
        task_name="onadata.apps.logger.tasks.commit_cached_elist_num_entities_async",
    )


def commit_cached_elist_num_entities() -> None:
    """Commit cached EntityList `num_entities` counter to the database

    Commit is successful if no other process holds the lock
    """
    commit_cached_counters(
        model=EntityList,
        field_name="num_entities",
        key_prefix=ELIST_NUM_ENTITIES,
        tracked_ids_key=ELIST_NUM_ENTITIES_IDS,
        lock_key=ELIST_NUM_ENTITIES_LOCK,
        created_at_key=ELIST_NUM_ENTITIES_CREATED_AT,
    )
