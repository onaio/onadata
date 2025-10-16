"""
Management command to import Entities from a CSV file.

CSV requirements:
- A required column named "label" for the Entity label
- An optional column named "uuid" for the Entity uuid
- All other columns are treated as dataset properties and must exist in the
  target `EntityList.properties` (columns that don't exist will cause a row
  error via serializer validation)

Usage:
    python manage.py import_entities --entity-list <id> [--created-by <username>] path/to/file.csv

Options:
- --dry-run: validate and report without saving anything
"""

import csv
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _

from onadata.apps.logger.models import EntityList
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

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        entity_list_id = options["entity_list_id"]
        created_by = options["created_by"]
        dry_run = options["dry_run"]

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
        error_rows: list[tuple[int, str]] = []

        try:
            with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(csv_file)

                if reader.fieldnames is None:
                    raise CommandError(_(f"CSV file {csv_path} is missing headers."))

                # Normalize headers: strip whitespace
                headers = [h.strip() for h in reader.fieldnames]

                # label is required; uuid optional; others treated as properties
                if "label" not in [h.lower() for h in headers]:
                    raise CommandError(_("CSV must include a 'label' column."))

                # Map original header names to canonical keys
                # Preserve case for properties, but detect label/uuid case-insensitively
                def header_key(key: str) -> str:
                    k = key.strip()
                    lower = k.lower()
                    if lower == "label":
                        return "label"
                    if lower == "uuid":
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
                    data = {}
                    for k, v in row.items():
                        if k in {"label", "uuid"}:
                            continue
                        value = None if v is None else str(v).strip()
                        if value == "":
                            # Skip empty values; create() will drop falsy values anyway
                            continue
                        data[k] = value

                    serializer = EntitySerializer(
                        data={"label": label, "uuid": uuid_value, "data": data},
                        context={
                            "entity_list": entity_list,
                            # Minimal request-like object to satisfy serializer history creation
                            "request": SimpleNamespace(user=user),
                        },
                    )

                    try:
                        serializer.is_valid(raise_exception=True)
                        if not dry_run:
                            serializer.save()
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

        action = "validated" if dry_run else "created"
        self.stdout.write(_(f"Successfully {action} {created_count} row(s)."))

        if error_rows:
            # Non-zero exit to signal partial failure
            raise CommandError(_(f"{len(error_rows)} row(s) failed."))
