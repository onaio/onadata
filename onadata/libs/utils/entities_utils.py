import csv
import importlib
import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Iterator, TextIO

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet
from django.utils.translation import gettext as _

from onadata.apps.logger.models import (
    Entity,
    EntityHistory,
    EntityList,
    Instance,
    RegistrationForm,
)
from onadata.apps.logger.xform_instance_parser import (
    get_entity_group_data,
    get_entity_label_from_node,
    get_entity_nodes_from_xml,
)
from onadata.libs.exceptions import CSVImportError
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
    instance: Instance, registration_form: RegistrationForm, entity_node
) -> dict:
    """Parses Instance data and returns Entity json for a single entity node

    A submission can create more than one Entity when the entity is defined
    within a repeat, so the Entity json is built from the fields belonging to
    the entity node's group.

    :param instance: Instance to create Entity from
    :param registration_form: RegistrationForm to create Entity from
    :param entity_node: The submission's entity XML node
    :return: Entity properties
    """
    # Getting a mapping of save_to field to the field name
    mapped_properties = registration_form.get_save_to(instance.version)
    # Field names with an alias defined mapped to the alias
    field_alias = {field: alias for alias, field in mapped_properties.items()}
    group_data = get_entity_group_data(entity_node, instance.get_dict())
    entity_json: dict[str, Any] = {}

    for field_name, field_data in group_data.items():
        # We extract field names within grouped sections
        ungrouped_field_name = field_name.split("/")[-1]

        if ungrouped_field_name in field_alias:
            entity_json[field_alias[ungrouped_field_name]] = field_data

    label = get_entity_label_from_node(entity_node)

    # An update submission may omit the label, leaving it unchanged
    if label is not None:
        entity_json["label"] = label

    return entity_json


def _create_entity_from_instance(
    instance: Instance, registration_form: RegistrationForm, entity_node
) -> Entity:
    """Create an Entity

    :param instance: Submission from which the Entity is created from
    :param registration_form: RegistrationForm creating the Entity
    :param entity_node: The submission's entity XML node
    :return: A newly created Entity
    """
    entity_json = get_entity_json_from_instance(
        instance, registration_form, entity_node
    )
    entity_list = registration_form.entity_list
    entity = Entity.objects.create(
        entity_list=entity_list,
        json=entity_json,
        uuid=entity_node.getAttribute("id"),
    )
    entity.history.create(
        registration_form=registration_form,
        xml=instance.xml,
        instance=instance,
        form_version=instance.version,
        json=entity_json,
        created_by=instance.user,
        mutation_type=EntityHistory.MutationType.CREATE,
    )

    return entity


def _update_entity_from_instance(
    entity: Entity,
    instance: Instance,
    registration_form: RegistrationForm,
    entity_node,
) -> Entity:
    """Updates Entity

    :param entity: Entity to be updated
    :param instance: Submission that updates an Entity
    :param registration_form: RegistrationForm updating the Entity
    :param entity_node: The submission's entity XML node
    :return: updated Entity if uuid valid, else None
    """
    patch_data = get_entity_json_from_instance(instance, registration_form, entity_node)
    entity.json = {**entity.json, **patch_data}
    entity.save()
    entity.history.create(
        registration_form=registration_form,
        xml=instance.xml,
        instance=instance,
        form_version=instance.version,
        json=entity.json,
        created_by=instance.user,
        mutation_type=EntityHistory.MutationType.UPDATE,
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
    entity_nodes = get_entity_nodes_from_xml(instance.xml)

    if not registration_form_qs.exists() or not entity_nodes:
        return

    registration_form = registration_form_qs.first()
    mutation_success_checks = ["1", "true"]

    # A repeat can create multiple Entities in the same EntityList
    for entity_node in entity_nodes:
        entity_uuid = entity_node.getAttribute("id")

        if not entity_uuid:
            continue

        try:
            entity = Entity.objects.get(
                uuid=entity_uuid, entity_list=registration_form.entity_list
            )
        except Entity.DoesNotExist:
            if entity_node.getAttribute("create") in mutation_success_checks:
                # Create Entity
                _create_entity_from_instance(instance, registration_form, entity_node)

        else:
            if entity_node.getAttribute("update") in mutation_success_checks:
                # Update Entity
                _update_entity_from_instance(
                    entity, instance, registration_form, entity_node
                )


def adjust_elist_num_entities(entity_list: EntityList, delta: int) -> None:
    """Adjust EntityList `num_entities` counter

    :param entity_list: EntityList
    :param delta: Value to increment or decrement by
    """
    adjust_counter(
        pk=entity_list.pk,
        model=EntityList,
        field_name="num_entities",
        delta=delta,
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


@dataclass
class RowResult:
    index: int  # Row index
    status: str  # "created" | "updated" | "error"
    error: str | None = None  # error message if status == "error"


# pylint: disable=too-many-locals,too-many-positional-arguments
# pylint: disable=too-many-arguments,too-many-branches
def import_entities_from_csv(
    entity_list: EntityList,
    csv_file: TextIO,
    label_column: str = "label",
    uuid_column: str = "uuid",
    user: AbstractBaseUser | None = None,
    dry_run: bool = False,
) -> Iterator[RowResult]:
    """Import Entities from a CSV file

    :param entity_list: EntityList to import Entities to
    :param csv_file: CSV file to import Entities from
    :param label_column: Column name to use as Entity label
    :param uuid_column: Column name to use as Entity UUID
    :param user: User to attribute the Entities to
    :param dry_run: If True, do not save the Entities
    :return: tuple of created_count, updated_count, error_rows
    :raises ValueError: If CSV file is missing headers or label column is missing
    """
    entity_serializer_module = importlib.import_module(
        "onadata.libs.serializers.entity_serializer"
    )

    if not entity_list.properties:
        raise CSVImportError("EntityList has no properties defined.")

    reader = csv.DictReader(csv_file)
    # Normalize headers: strip whitespace
    headers = [h.strip() for h in reader.fieldnames]

    # Check if the specified label column exists
    if label_column.lower() not in [h.lower() for h in headers]:
        raise CSVImportError(_(f"CSV must include a '{label_column}' column."))

    # Map original header names to canonical keys
    # Preserve case for properties, but detect label/uuid case-insensitively
    def header_key(key: str) -> str:
        k = key.strip()
        lower = k.lower()

        if lower == label_column.lower():
            return "label"
        if lower == uuid_column.lower():
            return "uuid"
        return k

    for row_index, raw_row in enumerate(
        reader, start=2
    ):  # start=2 accounts for header row
        # Build normalized row dict
        row = {header_key(k): v for k, v in raw_row.items()}

        label = (row.get("label") or "").strip()
        uuid_value = (row.get("uuid") or "").strip() or None

        # Extract properties: everything except label/uuid
        # Only include properties that are valid for this EntityList
        valid_properties = set(entity_list.properties)
        properties = {}

        for k, v in row.items():
            if k in {"label", "uuid"}:
                continue

            # Skip unknown properties silently
            if k not in valid_properties:
                continue

            value = None if v is None else str(v).strip()

            if value == "":
                # Skip empty values; create() will drop falsy values anyway
                continue

            properties[k] = value

        data = {"label": label, "data": properties}

        if uuid_value:
            data["uuid"] = uuid_value

        existing_entity = None

        if uuid_value:
            # Check if Entity already exists with this uuid
            try:
                existing_entity = Entity.objects.get(
                    entity_list=entity_list,
                    uuid=uuid_value,
                    deleted_at__isnull=True,
                )
            except Entity.DoesNotExist:
                pass

        if not existing_entity and not properties:
            yield RowResult(
                index=row_index,
                status="error",
                error="At least 1 property is required to create Entity",
            )
            continue

        serializer = entity_serializer_module.EntitySerializer(
            instance=existing_entity,
            data=data,
            context={
                "entity_list": entity_list,
                # Minimal request-like object
                "request": SimpleNamespace(user=user),
            },
        )

        try:
            serializer.is_valid(raise_exception=True)

            if not dry_run:
                serializer.save()

            yield RowResult(
                index=row_index,
                status="updated" if existing_entity else "created",
            )

        except Exception as exc:  # pylint: disable=broad-except
            yield RowResult(index=row_index, status="error", error=str(exc))
