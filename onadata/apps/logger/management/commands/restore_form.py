"""
Restore a soft-deleted XForm object.
"""

from django.core.management.base import BaseCommand, CommandError

from onadata.apps.logger.models import XForm


class Command(BaseCommand):
    """
    Management command to restore soft-deleted XForm objects.

    Usage:
    python manage.py restore_form <form_id>
    """

    help = "Restores a soft-deleted XForm."

    def add_arguments(self, parser):
        # Add an argument to specify the form ID
        parser.add_argument(
            "form_id",
            type=int,
            help="The ID of the soft-deleted form to restore",
        )

    def handle(self, *args, **options):
        form_id = options["form_id"]

        try:
            # Retrieve the soft-deleted form
            xform = XForm.objects.get(pk=form_id)

            if xform.deleted_at is None:
                raise CommandError(f"Form with ID {form_id} is not soft-deleted")

            # Perform the restoration
            self.stdout.write(f"Restoring form with ID {form_id}...")
            was_deleted_by = xform.deleted_by.username if xform.deleted_by else None
            # was_deleted_at in the format Nov. 1, 2021, HH:MM UTC
            was_deleted_at = xform.deleted_at.strftime("%b. %d, %Y, %H:%M UTC")
            xform.restore()

            # Display success message
            success_msg = (
                f"Successfully restored form '{xform.id_string}' with "
                f"ID {form_id} deleted by {was_deleted_by} at {was_deleted_at}."
            )
            self.stdout.write(self.style.SUCCESS(success_msg))

        except XForm.DoesNotExist as exc:
            raise CommandError(f"Form with ID {form_id} does not exist") from exc

        except Exception as exc:
            raise CommandError(
                f"An error occurred while restoring the form: {exc}"
            ) from exc
