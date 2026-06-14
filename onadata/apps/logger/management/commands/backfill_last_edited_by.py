# -*- coding: utf-8 -*-
"""Backfill last_edited_by on existing edited submissions."""

from django.core.management import BaseCommand
from django.utils.translation import gettext_lazy

from multidb.pinning import use_master

from onadata.apps.logger.models import Instance, InstanceHistory


class Command(BaseCommand):
    """Backfill last edited by field on existing submissions."""

    help = gettext_lazy("Backfill last edited by values on edited submissions.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            default=1000,
            type=int,
            help="Number of edited submissions to process per batch.",
        )

    @use_master
    def handle(self, *args, **options):
        updated_total = 0
        processed_total = 0
        batch_size = max(1, int(options.get("batch_size", 1000)))
        ids = []
        ids_query = Instance.objects.filter(
            last_edited__isnull=False,
            last_edited_by__isnull=True,
            submission_history__user__isnull=False,
        ).values_list("pk", flat=True)
        ids_query = ids_query.distinct()
        for instance_id in ids_query.iterator():
            ids.append(instance_id)
            if len(ids) >= batch_size:
                updated_total += self._process_batch(ids)
                processed_total += len(ids)
                ids = []
        if ids:
            updated_total += self._process_batch(ids)
            processed_total += len(ids)

        self.stdout.write(
            f"Processed {processed_total} edited submission(s). Updated "
            f"{updated_total} last edited by value(s)."
        )

    def _instance_history_query(self):
        """Return base query for instance history rows."""
        return InstanceHistory.objects.all()

    def _process_batch(self, instance_ids):
        last_edited_by_map = self._latest_history_user_by_instance(instance_ids)
        existing_instances = dict(
            Instance.objects.filter(pk__in=instance_ids).values_list(
                "pk", "last_edited_by_id"
            )
        )
        instances_to_update = []

        for instance_id in instance_ids:
            latest_editor = last_edited_by_map.get(instance_id)
            if latest_editor is not None and latest_editor != existing_instances.get(
                instance_id
            ):
                instances_to_update.append(
                    Instance(pk=instance_id, last_edited_by_id=latest_editor)
                )

        if instances_to_update:
            Instance.objects.bulk_update(instances_to_update, ["last_edited_by"])

        return len(instances_to_update)

    @staticmethod
    def _latest_history_user_by_instance(instance_ids):
        history_query = InstanceHistory.objects.filter(
            xform_instance_id__in=instance_ids, user__isnull=False
        ).order_by("xform_instance_id", "-date_created")

        last_edited_by = {}
        for history in history_query.iterator():
            if history.xform_instance_id not in last_edited_by:
                last_edited_by[history.xform_instance_id] = history.user_id

        return last_edited_by
