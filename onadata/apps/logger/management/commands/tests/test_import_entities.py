"""Tests for management command import_entities"""

import os
from io import StringIO
from tempfile import NamedTemporaryFile

from django.core.management import call_command
from django.core.management.base import CommandError

from onadata.apps.logger.models import Entity, EntityList
from onadata.apps.main.tests.test_base import TestBase


class ImportEntitiesCommandTestCase(TestBase):
    """Tests for importing Entities from CSV"""

    def setUp(self):
        super().setUp()
        # Ensure a project exists and a registration form that defines an EntityList
        self._publish_registration_form(self.user)
        # Retrieve the created EntityList (list_name was 'trees' in helper)
        self.entity_list = EntityList.objects.get(name="trees", project=self.project)

    def _write_csv(self, header, rows):
        tmp = NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", newline="")
        try:
            tmp.write(",".join(header) + "\n")
            for r in rows:
                tmp.write(",".join(r) + "\n")
        finally:
            tmp.close()
        self.addCleanup(lambda: os.path.exists(tmp.name) and os.unlink(tmp.name))
        return tmp.name

    def test_import_entities_success(self):
        """Successfully imports entities from CSV using allowed properties"""
        csv_path = self._write_csv(
            ["label", "species", "circumference_cm"],
            [
                ["300cm purpleheart", "purpleheart", "300"],
                ["200cm mora", "mora", "200"],
            ],
        )

        out = StringIO()
        call_command(
            "import_entities",
            "--entity-list",
            str(self.entity_list.pk),
            "--created-by",
            self.user.username,
            csv_path,
            stdout=out,
        )

        entities = Entity.objects.filter(entity_list=self.entity_list).order_by("pk")
        self.assertEqual(entities.count(), 2)
        self.assertEqual(entities[0].json.get("label"), "300cm purpleheart")
        self.assertEqual(entities[0].json.get("species"), "purpleheart")
        self.assertEqual(entities[0].json.get("circumference_cm"), "300")
        self.assertEqual(entities[1].json.get("label"), "200cm mora")

    def test_import_entities_dry_run(self):
        """Dry-run validates but does not create entities"""
        csv_path = self._write_csv(
            ["label", "species", "circumference_cm"],
            [["300cm purpleheart", "purpleheart", "300"]],
        )

        pre_count = Entity.objects.filter(entity_list=self.entity_list).count()

        out = StringIO()
        call_command(
            "import_entities",
            "--entity-list",
            str(self.entity_list.pk),
            "--dry-run",
            csv_path,
            stdout=out,
        )

        post_count = Entity.objects.filter(entity_list=self.entity_list).count()
        self.assertEqual(pre_count, post_count)
        self.assertIn("validated", out.getvalue())

    def test_missing_label_header(self):
        """CSV without 'label' header raises CommandError"""
        csv_path = self._write_csv(["species"], [["purpleheart"]])
        with self.assertRaises(CommandError):
            call_command(
                "import_entities",
                "--entity-list",
                str(self.entity_list.pk),
                csv_path,
            )

    def test_invalid_created_by(self):
        """Invalid created-by username raises CommandError"""
        csv_path = self._write_csv(
            ["label", "species"],
            [["300cm purpleheart", "purpleheart"]],
        )
        with self.assertRaises(CommandError):
            call_command(
                "import_entities",
                "--entity-list",
                str(self.entity_list.pk),
                "--created-by",
                "does_not_exist",
                csv_path,
            )

    def test_invalid_property_column(self):
        """Unknown property should cause row validation error and abort with CommandError"""
        csv_path = self._write_csv(
            ["label", "unknown_property"],
            [["some label", "value"]],
        )
        with self.assertRaises(CommandError):
            call_command(
                "import_entities",
                "--entity-list",
                str(self.entity_list.pk),
                csv_path,
            )
        self.assertEqual(Entity.objects.filter(entity_list=self.entity_list).count(), 0)

    def test_import_entities_with_uuid(self):
        """Imports entities with uuid"""
        csv_path = self._write_csv(
            ["label", "species", "circumference_cm", "uuid"],
            [
                [
                    "300cm purpleheart",
                    "purpleheart",
                    "300",
                    "dbee4c32-a922-451c-9df7-42f40bf78f48",
                ]
            ],
        )
        call_command(
            "import_entities",
            "--entity-list",
            str(self.entity_list.pk),
            csv_path,
        )
        entities = Entity.objects.filter(entity_list=self.entity_list).order_by("pk")
        self.assertEqual(entities.count(), 1)
        self.assertEqual(entities[0].json.get("label"), "300cm purpleheart")
        self.assertEqual(entities[0].json.get("species"), "purpleheart")
        self.assertEqual(entities[0].json.get("circumference_cm"), "300")
        self.assertEqual(str(entities[0].uuid), "dbee4c32-a922-451c-9df7-42f40bf78f48")
