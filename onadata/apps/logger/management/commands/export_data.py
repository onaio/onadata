# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from onadata.apps.logger.models.xform import XForm
from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.export_tools import generate_export

from codetiming import Timer


class Command(BaseCommand):
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
            with Timer() as t:
                export = generate_export(Export.CSV_EXPORT, xform)
            elapsed_time = t.last
            self.stdout.write(
                self.style.NOTICE(
                    f"The file {export.full_filepath} was exported in {elapsed_time:.2f} seconds."
                )
            )
            plural_or_singular = (
                "submission" if xform.num_of_submissions == 1 else "submissions"
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'{export.pk}: Exporting {xform.num_of_submissions} {plural_or_singular} of the form "{xform.title}"'
                )
            )
