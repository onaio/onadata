"""Tests for management command restore_original_submissions."""

import os
from io import BytesIO, StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from onadata.apps.logger.models import Instance, InstanceHistory, XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.parsed_instance import ParsedInstance
from onadata.libs.utils.logger_tools import create_instance

FIXTURES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "../../../fixtures/tutorial"
)
ORIGINAL_UUID = "729f173c688e482486a48661700455ff"
LATEST_UUID = "6e3a2d84-9780-4549-a0de-974a257276a6"
ORIGINAL_GPS = "-1.2836198 36.8795437 0.0 1044.0"
ORIGINAL_LAT = -1.2836198
OTHER_FORM_UUID = "5b2cc313-fc09-437e-8149-fcd32f695d41"


class RestoreOriginalSubmissionsTestCase(TestBase):
    def setUp(self):
        super().setUp()
        self._publish_xls_file_and_set_xform(
            os.path.join(FIXTURES_DIR, "tutorial.xlsx")
        )
        self.out = StringIO()

        for filename in (
            "tutorial_2012-06-27_11-27-53_w_uuid.xml",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited_again.xml",
        ):
            self._make_submission(self._submission_file(filename))

        self.instance = Instance.objects.get(xform=self.xform)
        self.original = self.instance.submission_history.order_by(
            "date_created", "pk"
        ).first()

        self.assertEqual(self.instance.uuid, LATEST_UUID)
        self.assertEqual(self.instance.submission_history.count(), 2)
        self.assertEqual(self.original.uuid, ORIGINAL_UUID)
        self.assertNotEqual(self.instance.xml, self.original.xml)

    def _submission_file(self, filename):
        return os.path.join(FIXTURES_DIR, "instances", filename)

    def _call_command(self, option, value, commit=True):
        args = [option, str(value)]

        if commit:
            args.append("--commit-changes")

        call_command("restore_original_submissions", *args, stdout=self.out)

    def _restore(self, instance_ids, commit=True):
        self._call_command("--instance-ids", instance_ids, commit)

    def _make_unedited_submission(self):
        self._make_submission(self._submission_file("tutorial_2012-06-27_11-27-53.xml"))
        unedited = Instance.objects.exclude(pk=self.instance.pk).get(xform=self.xform)
        self.assertFalse(unedited.submission_history.exists())

        return unedited

    def _make_edited_submission_in_another_form(self):
        md = """
        | survey |      |      |       |
        |        | type | name | label |
        |        | text | name | Name  |
        """
        form = self._publish_markdown(md, self.user)
        xml = (
            f'<data id="{form.id_string}"><meta>'
            "<instanceID>uuid:{uuid}</instanceID></meta>"
            "<name>{name}</name></data>"
        )
        edited = create_instance(
            self.user.username,
            BytesIO(xml.format(uuid=OTHER_FORM_UUID, name="edited").encode("utf-8")),
            media_files=[],
        )
        InstanceHistory.objects.create(
            xform_instance=edited,
            xml=xml.format(uuid="b3f1c2d4", name="original"),
            uuid="b3f1c2d4",
            checksum="b3f1c2d4",
        )
        self.assertNotEqual(edited.xform_id, self.xform.pk)

        return edited

    def test_restores_original_version(self):
        parsed_instance = ParsedInstance.objects.get(instance=self.instance)
        self.assertNotEqual(self.instance.json["gps"], ORIGINAL_GPS)
        self.assertNotAlmostEqual(parsed_instance.lat, ORIGINAL_LAT)
        self.assertEqual(self.instance.last_edited_by, self.user)

        self._restore(self.instance.pk)

        self.instance.refresh_from_db()
        parsed_instance.refresh_from_db()
        self.assertEqual(self.instance.xml, self.original.xml)
        self.assertEqual(self.instance.uuid, ORIGINAL_UUID)
        self.assertEqual(self.instance.checksum, self.original.checksum)
        self.assertEqual(self.instance.json["gps"], ORIGINAL_GPS)
        self.assertEqual(self.instance.json["_uuid"], ORIGINAL_UUID)
        self.assertAlmostEqual(parsed_instance.lat, ORIGINAL_LAT)
        self.assertIsNone(self.instance.last_edited_by)
        self.assertIn(f"{self.instance.pk}: restored", self.out.getvalue())

    def test_keeps_replaced_version_in_history(self):
        replaced_xml = self.instance.xml
        replaced_checksum = self.instance.checksum

        self._restore(self.instance.pk)

        self.assertEqual(self.instance.submission_history.count(), 3)
        latest = self.instance.submission_history.order_by("-date_created").first()
        self.assertEqual(latest.xml, replaced_xml)
        self.assertEqual(latest.uuid, LATEST_UUID)
        self.assertEqual(latest.checksum, replaced_checksum)

    def test_dry_run_changes_nothing(self):
        xml_before = self.instance.xml

        self._restore(self.instance.pk, commit=False)

        self.instance.refresh_from_db()
        self.assertEqual(self.instance.xml, xml_before)
        self.assertEqual(self.instance.uuid, LATEST_UUID)
        self.assertEqual(self.instance.submission_history.count(), 2)
        self.assertIn(
            f"{self.instance.pk}: would restore uuid {ORIGINAL_UUID}",
            self.out.getvalue(),
        )

    def test_restores_each_listed_submission(self):
        unedited = self._make_unedited_submission()

        self._restore(f"{self.instance.pk},{unedited.pk}")

        self.instance.refresh_from_db()
        self.assertEqual(self.instance.uuid, ORIGINAL_UUID)
        output = self.out.getvalue()
        self.assertIn(f"{self.instance.pk}: restored", output)
        self.assertIn(f"{unedited.pk}: skipped, no history", output)

    def test_restores_only_edited_submissions_of_form(self):
        self._make_unedited_submission()
        in_another_form = self._make_edited_submission_in_another_form()

        self._call_command("--form-id", self.xform.pk)

        self.instance.refresh_from_db()
        in_another_form.refresh_from_db()
        self.assertEqual(self.instance.uuid, ORIGINAL_UUID)
        self.assertEqual(in_another_form.uuid, OTHER_FORM_UUID)
        self.assertEqual(
            self.out.getvalue().splitlines(), [f"{self.instance.pk}: restored"]
        )

    def test_rejects_unknown_form(self):
        missing_form_id = XForm.objects.order_by("-pk").first().pk + 1

        with self.assertRaises(CommandError):
            self._call_command("--form-id", missing_form_id)

    def test_skips_deleted_submission(self):
        self.instance.set_deleted(timezone.now(), self.user)

        self._restore(self.instance.pk)

        self.instance.refresh_from_db()
        self.assertEqual(self.instance.uuid, LATEST_UUID)
        self.assertEqual(self.instance.submission_history.count(), 2)
        self.assertIn(
            f"{self.instance.pk}: skipped, not found or deleted", self.out.getvalue()
        )

    def test_skips_history_without_uuid(self):
        InstanceHistory.objects.filter(pk=self.original.pk).update(uuid="")

        self._restore(self.instance.pk)

        self.instance.refresh_from_db()
        self.assertEqual(self.instance.uuid, LATEST_UUID)
        self.assertEqual(self.instance.submission_history.count(), 2)
        self.assertIn(
            f"{self.instance.pk}: skipped, history row {self.original.pk} "
            "lacks uuid or checksum",
            self.out.getvalue(),
        )

    def test_skips_encrypted_first_version(self):
        InstanceHistory.objects.filter(pk=self.original.pk).update(
            xml=(
                '<tutorial id="tutorial" encrypted="yes"><meta>'
                f"<instanceID>uuid:{ORIGINAL_UUID}</instanceID>"
                "</meta></tutorial>"
            )
        )

        self._restore(self.instance.pk)

        self.instance.refresh_from_db()
        self.assertEqual(self.instance.uuid, LATEST_UUID)
        self.assertEqual(self.instance.submission_history.count(), 2)
        self.assertIn(
            f"{self.instance.pk}: skipped, first version is encrypted",
            self.out.getvalue(),
        )

    def test_skips_already_restored_submission(self):
        self._restore(self.instance.pk)
        self.assertEqual(self.instance.submission_history.count(), 3)

        self._restore(self.instance.pk)

        self.assertEqual(self.instance.submission_history.count(), 3)
        self.assertIn(
            f"{self.instance.pk}: skipped, already the original", self.out.getvalue()
        )

    def test_failure_is_rolled_back(self):
        unedited = self._make_unedited_submission()
        XForm.objects.filter(pk=self.xform.pk).update(downloadable=False)

        self._restore(f"{self.instance.pk},{unedited.pk}")

        self.instance.refresh_from_db()
        self.assertEqual(self.instance.uuid, LATEST_UUID)
        self.assertEqual(self.instance.submission_history.count(), 2)
        output = self.out.getvalue()
        self.assertIn(
            f"{self.instance.pk}: failed, FormInactiveError: Form is inactive", output
        )
        self.assertIn(f"{unedited.pk}: skipped, no history", output)

    def test_rejects_non_numeric_ids(self):
        with self.assertRaises(CommandError):
            self._restore(f"{self.instance.pk},abc")

        self.instance.refresh_from_db()
        self.assertEqual(self.instance.uuid, LATEST_UUID)
