# -*- coding: utf-8 -*-
"""
Tests for the onadata.apps.logger.management.commands.export_data module.
"""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.export import Export


class ExportDataTest(TestBase):
    """Tests for the export_data management command."""

    def test_command_output(self):
        """Test the output of the export_data management command."""
        output = StringIO()
        error_output = StringIO()
        with self.assertRaisesMessage(
            CommandError,
            expected_message="Error: the following arguments are required: form_id",
        ):
            _ = call_command("export_data", stdout=output)

        _ = call_command("export_data", 12300, stdout=output, stderr=error_output)
        self.assertIn("Exporting ...", output.getvalue())
        self.assertIn(
            "There is no form with id 12300 present.", error_output.getvalue()
        )
        self._publish_transportation_form_and_submit_instance()
        export_count = Export.objects.filter().count()
        _ = call_command(
            "export_data", self.xform.pk, stdout=output, stderr=error_output
        )
        self.assertIn(
            f'Exporting 1 submission of the form "{self.xform.title}"',
            output.getvalue(),
        )
        # confirm a new export record was created.
        self.assertEqual(Export.objects.filter().count(), export_count + 1)
        export = Export.objects.filter(
            xform_id=self.xform.pk, export_type=Export.CSV_EXPORT
        ).latest("created_on")
        self.assertIn(
            f"The file {export.full_filepath} was exported in",
            output.getvalue(),
        )
