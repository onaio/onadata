"""
Management command to import Entities from a CSV file.

Usage:
    python manage.py import_entities --entity-list <id>
    [--created-by <username>] [--dry-run] path/to/file.csv

Options:
--entity-list: the id of the EntityList to import entities to
--created-by: optional username of the user to attribute the entities to
--dry-run: validate and report without saving anything
--label-column: column name to use as Entity label (default: 'label')
--uuid-column: column name to use as Entity UUID (default: 'uuid')
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _

from onadata.apps.logger.models import EntityList
from onadata.apps.messaging.constants import ENTITY_LIST, ENTITY_LIST_IMPORTED
from onadata.apps.messaging.serializers import send_message
from onadata.libs.utils.entities_utils import import_entities_from_csv


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

        created, updated = 0
        errors = []

        try:
            with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as csv_file:
                try:
                    for row_result in import_entities_from_csv(
                        entity_list=entity_list,
                        csv_file=csv_file,
                        label_column=label_column,
                        uuid_column=uuid_column,
                        user=user,
                        dry_run=dry_run,
                    ):
                        if row_result.status == "created":
                            created += 1

                        elif row_result.status == "updated":
                            updated += 1

                        else:
                            errors.append(
                                (row_result.index, row_result.error or "Unknown error")
                            )
                except Exception as exc:  # pylint: disable=broad-except
                    raise CommandError(str(exc)) from exc
        except FileNotFoundError as error:
            raise CommandError(_(f"CSV file not found: {csv_path}")) from error

        # Output summary
        if errors:
            self.stdout.write("")
            self.stdout.write(_(f"Encountered {len(errors)} error(s):"))
            for line_no, err in errors[:50]:  # cap printed errors
                self.stdout.write(_(f"  Row {line_no}: {err}"))
            if len(errors) > 50:
                self.stdout.write(_(f"  ... and {len(errors) - 50} more"))

        if dry_run:
            self.stdout.write(_(f"Successfully validated {created + updated} row(s)."))
        else:
            if created > 0:
                self.stdout.write(_(f"Successfully created {created} entity(ies)."))
            if updated > 0:
                self.stdout.write(_(f"Successfully updated {updated} entity(ies)."))

            # Send message if import was successful and not dry-run
            if created > 0 or updated > 0:
                send_message(
                    instance_id=entity_list.pk,
                    target_id=entity_list.pk,
                    target_type=ENTITY_LIST,
                    user=user,
                    message_verb=ENTITY_LIST_IMPORTED,
                )

        if errors:
            # Non-zero exit to signal partial failure
            raise CommandError(_(f"{len(errors)} row(s) failed."))
