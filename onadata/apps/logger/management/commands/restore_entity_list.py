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
    python manage.py restore_entity_list --xform-id <xform_id>
    """

    help = "Restores a soft-deleted EntityList."

    def add_arguments(self, parser):
        # Add an argument to specify the EntityList ID
        parser.add_argument(
            "entity_list_id",
            type=int,
            nargs="?",
            help="The ID of the soft-deleted EntityList to restore",
        )
        parser.add_argument(
            "--xform-id",
            type=int,
            help=(
                "The ID of a registration form (XForm) that creates entities "
                "in the soft-deleted EntityList to restore"
            ),
        )

    def _get_entity_list(self, options):
        """Retrieve the soft-deleted EntityList to restore"""
        entity_list_id = options["entity_list_id"]
        xform_id = options["xform_id"]

        if (entity_list_id is None) == (xform_id is None):
            raise CommandError("Provide exactly one of entity_list_id or --xform-id")

        if entity_list_id is not None:
            try:
                entity_list = EntityList.objects.get(pk=entity_list_id)

            except EntityList.DoesNotExist as exc:
                raise CommandError(
                    f"EntityList with ID {entity_list_id} does not exist"
                ) from exc

            if entity_list.deleted_at is None:
                raise CommandError(
                    f"EntityList with ID {entity_list_id} is not soft-deleted"
                )

            return entity_list

        entity_lists = list(
            EntityList.objects.filter(
                registration_forms__xform_id=xform_id, deleted_at__isnull=False
            ).order_by("pk")
        )

        if not entity_lists:
            raise CommandError(
                f"No soft-deleted EntityList found for XForm with ID {xform_id}"
            )

        if len(entity_lists) > 1:
            entity_list_ids = ", ".join(str(dataset.pk) for dataset in entity_lists)
            raise CommandError(
                f"Multiple soft-deleted EntityLists found for XForm with ID "
                f"{xform_id}: {entity_list_ids}. Restore using the EntityList ID."
            )

        return entity_lists[0]

    def handle(self, *args, **options):
        entity_list = self._get_entity_list(options)

        try:
            # Perform the restoration
            self.stdout.write(f"Restoring EntityList with ID {entity_list.pk}...")
            was_deleted_by = (
                entity_list.deleted_by.username if entity_list.deleted_by else None
            )
            # was_deleted_at in the format Nov. 1, 2021, HH:MM UTC
            was_deleted_at = entity_list.deleted_at.strftime("%b. %d, %Y, %H:%M UTC")
            entity_list.restore()

            # Display success message
            success_msg = (
                f"Successfully restored EntityList '{entity_list.name}' with "
                f"ID {entity_list.pk} deleted by {was_deleted_by} at "
                f"{was_deleted_at}."
            )
            self.stdout.write(self.style.SUCCESS(success_msg))

        except Exception as exc:
            raise CommandError(
                f"An error occurred while restoring the EntityList: {exc}"
            ) from exc
