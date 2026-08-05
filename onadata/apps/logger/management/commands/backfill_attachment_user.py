# -*- coding: utf-8 -*-
"""Backfill null Attachment.user from the submission's user.

The decryption path created attachments without the denormalised
``user`` column set. Repair existing rows by copying the submitting
user from the attachment's Instance.

Only forms holding a KMS key can have decrypted attachments, so the
repair is scoped to those. The ``is_managed`` flag is not used because
it can read False for previously-managed forms.
"""

from django.core.management import BaseCommand
from django.db.models import Exists, OuterRef
from django.utils.translation import gettext_lazy

from multidb.pinning import use_master

from onadata.apps.logger.models import Attachment, XFormKey


class Command(BaseCommand):
    """Backfill null attachment user values from submissions."""

    help = gettext_lazy("Backfill null attachment user values from submissions.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            default=1000,
            type=int,
            help="Number of attachments to update per batch.",
        )

    @use_master
    def handle(self, *args, **options):
        updated_total = 0
        batch_size = max(1, int(options.get("batch_size", 1000)))
        has_kms_key = XFormKey.objects.filter(xform_id=OuterRef("instance__xform_id"))
        rows = (
            Attachment.objects.filter(user__isnull=True, instance__user__isnull=False)
            .filter(Exists(has_kms_key))
            .values_list("pk", "instance__user_id")
        )
        attachments = []

        for attachment_id, user_id in rows.iterator():
            attachments.append(Attachment(pk=attachment_id, user_id=user_id))
            if len(attachments) >= batch_size:
                updated_total += self._update_batch(attachments)
                attachments = []
        if attachments:
            updated_total += self._update_batch(attachments)

        self.stdout.write(f"Updated {updated_total} attachment(s).")

    @staticmethod
    def _update_batch(attachments):
        Attachment.objects.bulk_update(attachments, ["user"])

        return len(attachments)
