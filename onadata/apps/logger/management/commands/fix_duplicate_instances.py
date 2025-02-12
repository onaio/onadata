#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8
"""
Fix duplicate instances by merging the attachments.
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils.translation import gettext_lazy

from onadata.apps.logger.models import Instance


class Command(BaseCommand):
    """Fix duplicate instances by merging the attachments."""

    help = gettext_lazy("Fix duplicate instances by merging the attachments.")

    def query_data(self, sql):
        """Return results of given ``sql`` query."""
        cursor = connection.cursor()
        cursor.execute(sql)
        yield from cursor.fetchall()

    # pylint: disable=too-many-locals
    def handle(self, *args, **kwargs):
        sql = (
            "select xform_id, uuid, COUNT(xform_id || uuid) "
            "from logger_instance group by xform_id, uuid "
            "HAVING COUNT(xform_id || uuid) > 1;"
        )
        total_count = 0
        total_deleted = 0
        for xform, uuid, dupes_count in self.query_data(sql):
            instances = Instance.objects.filter(xform_id=xform, uuid=uuid).order_by(
                "pk"
            )
            first = instances[0]
            xml = instances[0].xml
            is_mspray_form = xform == 80970
            all_matches = True
            for i in instances[1:]:
                if i.xml != xml:
                    all_matches = False

            # mspray is a special case because the uuid and xform are duplicate
            # but the XML differes on xform.uuid while the rest of the data
            # is a match, let's maintain the submission with the
            # correct xform.uuid.
            if is_mspray_form and not all_matches:
                first = instances.filter(xml__contains=xform.uuid).first()
                to_delete = instances.exclude(xml__contains=xform.uuid)
            else:
                to_delete = instances.exclude(pk=first.pk)

            media_files = list(first.attachments.values_list("media_file", flat=True))
            delete_count = 0
            for i in to_delete:
                delete_count += 1
                for attachment in i.attachments.all():
                    if attachment.media_file not in media_files:
                        attachment.instance = first
                        attachment.save()

            if delete_count >= dupes_count:
                raise AssertionError(
                    f"# of records to delete {delete_count} should be less than"
                    f" total # of duplicates {dupes_count}."
                )
            to_delete.delete()
            total_count += dupes_count
            total_deleted += delete_count
            self.stdout.write(
                f"deleted {xform}: {uuid} ({delete_count} of {dupes_count})."
            )

        self.stdout.write(f"done: deleted {total_deleted} of {total_count}")
