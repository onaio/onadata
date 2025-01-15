# -*- coding: utf-8 -*-
"""
Management command to export data from a form in CSV format.
"""

from django.core.management.base import BaseCommand

from codetiming import Timer

from onadata.apps.logger.models.xform import XForm
from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.export_tools import generate_export


class Command(BaseCommand):
    """Export data from a form in CSV format"""

    help = "Exports data from a form in CSV format"

    def add_arguments(self, parser):
        parser.add_argument("form_id", type=int)

    def handle(self, *args: str, **options: str):
        self.stdout.write(self.style.SUCCESS("Exporting ..."))
        form_id = options["form_id"]
        try:
            xform = XForm.objects.get(pk=form_id)
        except XForm.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(f"There is no form with id {form_id} present.")
            )
        else:
            with Timer() as timer:
                export = generate_export(Export.CSV_EXPORT, xform)
            elapsed_time = timer.last
            msg = (
                f"The file {export.full_filepath} was exported in "
                f"{elapsed_time:.2f} seconds."
            )
            self.stdout.write(self.style.NOTICE(msg))
            plural_or_singular = (
                "submission" if xform.num_of_submissions == 1 else "submissions"
            )
            msg = (
                f"{export.pk}: Exporting {xform.num_of_submissions} "
                f'{plural_or_singular} of the form "{xform.title}"'
            )
            self.stdout.write(self.style.SUCCESS(msg))
