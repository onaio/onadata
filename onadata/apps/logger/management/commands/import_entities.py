"""
Management command to import Entities from a CSV file.

Usage:
    python manage.py import_entities --entity-list <id>
    [--created-by <username>] [--dry-run] path/to/file.csv

Options:
- --entity-list: the id of the EntityList to import entities to
- --created-by: optional username of the user to attribute the entities to
- --dry-run: validate and report without saving anything
"""

import csv
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _

from onadata.apps.logger.models import Entity, EntityList
from onadata.libs.serializers.entity_serializer import EntitySerializer


class Command(BaseCommand):
    """Import Entities from a CSV into a given EntityList."""

    help = _("Import Entities from a CSV file into a specified EntityList.")

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to CSV file")
        parser.add_argument(
            "--entity-list",
            type=int,
            required=True,
            dest="entity_list_id",
            help="ID of the EntityList (dataset) to save entities to",
        )
        parser.add_argument(
            "--created-by",
            type=str,
            required=False,
            dest="created_by",
            help="Optional username to attribute as creator for Entity history",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Validate only; do not create any Entities",
        )
        parser.add_argument(
            "--label-column",
            type=str,
            required=False,
            dest="label_column",
            help="Column name to use as Entity label (default: 'label')",
        )
        parser.add_argument(
            "--uuid-column",
            type=str,
            required=False,
            dest="uuid_column",
            help="Column name to use as Entity UUID (default: 'uuid')",
        )

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        entity_list_id = options["entity_list_id"]
        created_by = options["created_by"]
        dry_run = options["dry_run"]
        label_column = options["label_column"] or "label"
        uuid_column = options["uuid_column"] or "uuid"

        try:
            entity_list = EntityList.objects.get(
                pk=entity_list_id, deleted_at__isnull=True
            )
        except EntityList.DoesNotExist as error:
            raise CommandError(_(f"Invalid EntityList id {entity_list_id}")) from error

        user = None
        if created_by:
            try:
                user = get_user_model().objects.get(username=created_by)
            except get_user_model().DoesNotExist as error:
                raise CommandError(_(f"Invalid username {created_by}")) from error

        created_count = 0
        updated_count = 0
        error_rows: list[tuple[int, str]] = []

        try:
            with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(csv_file)

                if reader.fieldnames is None:
                    raise CommandError(_(f"CSV file {csv_path} is missing headers."))

                # Normalize headers: strip whitespace
                headers = [h.strip() for h in reader.fieldnames]

                # Check if the specified label column exists
                if label_column.lower() not in [h.lower() for h in headers]:
                    raise CommandError(
                        _(f"CSV must include a '{label_column}' column.")
                    )

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

                    # Check if Entity already exists with this uuid
                    existing_entity = None
                    if uuid_value:
                        try:
                            existing_entity = Entity.objects.get(
                                entity_list=entity_list,
                                uuid=uuid_value,
                                deleted_at__isnull=True,
                            )
                        except Entity.DoesNotExist:
                            pass

                    serializer = EntitySerializer(
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
                        if existing_entity:
                            updated_count += 1
                        else:
                            created_count += 1
                    except Exception as exc:  # pylint: disable=broad-except
                        error_rows.append((row_index, str(exc)))

        except FileNotFoundError as error:
            raise CommandError(_(f"CSV file not found: {csv_path}")) from error

        # Output summary
        if error_rows:
            self.stdout.write("")
            self.stdout.write(_(f"Encountered {len(error_rows)} error(s):"))
            for line_no, err in error_rows[:50]:  # cap printed errors
                self.stdout.write(_(f"  Row {line_no}: {err}"))
            if len(error_rows) > 50:
                self.stdout.write(_(f"  ... and {len(error_rows) - 50} more"))

        if dry_run:
            self.stdout.write(
                _(f"Successfully validated {created_count + updated_count} row(s).")
            )
        else:
            if created_count > 0:
                self.stdout.write(
                    _(f"Successfully created {created_count} entity(ies).")
                )
            if updated_count > 0:
                self.stdout.write(
                    _(f"Successfully updated {updated_count} entity(ies).")
                )

        if error_rows:
            # Non-zero exit to signal partial failure
            raise CommandError(_(f"{len(error_rows)} row(s) failed."))
