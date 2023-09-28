"""
Module containing the recover_deleted_attachments management command.

Used to recover attachments that were accidentally deleted within the system
but are still required/present within the submission XML

Sample usage: python manage.py recover_deleted_attachments --form 1
"""
from django.core.management.base import BaseCommand

from onadata.apps.logger.models import Instance


def recover_deleted_attachments(form_id: str, stdout=None):
    """
    Recovers attachments that were accidentally soft-deleted

    :param: (str) form_id: Unique identifier for an XForm object
    :param: (sys.stdout) stdout: Python standard output. Default: None
    """
    instances = Instance.objects.filter(xform__id=form_id, deleted_at__isnull=True)
    for instance in instances:
        expected_attachments = instance.get_expected_media()
        if not instance.attachments.filter(deleted_at__isnull=True).count() == len(
            expected_attachments
        ):
            attachments_to_recover = instance.attachments.filter(
                deleted_at__isnull=False, name__in=expected_attachments
            )
            for attachment in attachments_to_recover:
                attachment.deleted_at = None
                attachment.deleted_by = None
                attachment.save()

                if stdout:
                    stdout.write(f"Recovered {attachment.name} ID: {attachment.id}")
            # Regenerate instance JSON
            instance.json = instance.get_full_dict()
            instance.save()


class Command(BaseCommand):
    """
    Management command used to recover wrongfully deleted
    attachments.
    """

    help = "Restore wrongly deleted attachments"

    def add_arguments(self, parser):
        parser.add_argument("-f", "--form", dest="form_id", type=int)

    def handle(self, *args, **options):
        form_id = options.get("form_id")
        recover_deleted_attachments(form_id, self.stdout)
