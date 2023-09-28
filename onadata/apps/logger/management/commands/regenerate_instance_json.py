"""
Management command python manage.py regenerate_instance_json <form_ids>

Regenerates a form's instances json asynchronously
"""

from celery.result import AsyncResult

from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache

from onadata.apps.api.tasks import regenerate_form_instance_json
from onadata.apps.logger.models import XForm
from onadata.libs.utils.cache_tools import (
    XFORM_REGENERATE_INSTANCE_JSON_TASK,
    XFORM_REGENERATE_INSTANCE_JSON_TASK_TTL,
)


class Command(BaseCommand):
    """Regenerate a form's instances json

    Json data recreated afresh and any existing json data is overriden

    Usage:
    python manage.py regenerate_instance_json <form_ids> e.g
    python manage.py regenerate_instance_json 689 567 453
    """

    help = "Regenerate a form's instances json"

    def add_arguments(self, parser):
        parser.add_argument("form_ids", nargs="+", type=int)

    def handle(self, *args, **options):
        for form_id in options["form_ids"]:
            try:
                xform: XForm = XForm.objects.get(pk=form_id)

            except XForm.DoesNotExist:
                raise CommandError(  # pylint: disable=raise-missing-from
                    f"Form {form_id} does not exist"
                )

            self._regenerate_instance_json(xform)

    def _regenerate_instance_json(self, xform: XForm):
        if xform.is_instance_json_regenerated:
            # Async task completed successfully
            self.stdout.write(
                self.style.SUCCESS(f"Regeneration for {xform.pk} COMPLETE")
            )
            return

        cache_key = f"{XFORM_REGENERATE_INSTANCE_JSON_TASK}{xform.pk}"
        cached_task_id: str | None = cache.get(cache_key)

        if cached_task_id and AsyncResult(cached_task_id).state.upper() != "FAILURE":
            # FAILURE is the only state that should trigger regeneration if
            # a regeneration had earlier been triggered
            self.stdout.write(
                self.style.WARNING(f"Regeneration for {xform.pk} IN PROGRESS")
            )
            return

        # Task has either failed or does not exist in cache, we create a new async task
        # Celery backend expires the result after 1 day (24hrs) as outlined in the docs,
        # https://docs.celeryq.dev/en/latest/userguide/configuration.html#result-expires
        # If after 1 day you create an AsyncResult, the status will be PENDING.
        # We therefore set the cache timeout to 1 day same as the Celery backend result
        # expiry timeout
        result: AsyncResult = regenerate_form_instance_json.apply_async(args=[xform.pk])
        cache.set(
            cache_key,
            result.task_id,
            XFORM_REGENERATE_INSTANCE_JSON_TASK_TTL,
        )
        self.stdout.write(f"Regeneration for {xform.pk} STARTED")
