"""
Restore a soft-deleted EntityList object.
"""

from django.core.management.base import BaseCommand, CommandError

from onadata.apps.logger.models import EntityList


class Command(BaseCommand):
    """
    Management command to restore soft-deleted EntityList objects.

    Usage:
    python manage.py restore_entity_list <entity_list_id>
    """

    help = "Restores a soft-deleted EntityList."

    def add_arguments(self, parser):
        # Add an argument to specify the EntityList ID
        parser.add_argument(
            "entity_list_id",
            type=int,
            help="The ID of the soft-deleted EntityList to restore",
        )

    def handle(self, *args, **options):
        entity_list_id = options["entity_list_id"]

        try:
            # Retrieve the soft-deleted EntityList
            entity_list = EntityList.objects.get(pk=entity_list_id)

            if entity_list.deleted_at is None:
                raise CommandError(
                    f"EntityList with ID {entity_list_id} is not soft-deleted"
                )

            # Perform the restoration
            self.stdout.write(f"Restoring EntityList with ID {entity_list_id}...")
            was_deleted_by = (
                entity_list.deleted_by.username if entity_list.deleted_by else None
            )
            # was_deleted_at in the format Nov. 1, 2021, HH:MM UTC
            was_deleted_at = entity_list.deleted_at.strftime("%b. %d, %Y, %H:%M UTC")
            entity_list.restore()

            # Display success message
            success_msg = (
                f"Successfully restored EntityList '{entity_list.name}' with "
                f"ID {entity_list_id} deleted by {was_deleted_by} at "
                f"{was_deleted_at}."
            )
            self.stdout.write(self.style.SUCCESS(success_msg))

        except EntityList.DoesNotExist as exc:
            raise CommandError(
                f"EntityList with ID {entity_list_id} does not exist"
            ) from exc

        except Exception as exc:
            raise CommandError(
                f"An error occurred while restoring the EntityList: {exc}"
            ) from exc
