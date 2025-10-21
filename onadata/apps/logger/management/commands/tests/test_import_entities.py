"""Tests for management command import_entities"""

import os
from io import StringIO
from tempfile import NamedTemporaryFile
from unittest.mock import patch

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
        with NamedTemporaryFile(
            delete=False, mode="w", encoding="utf-8", newline=""
        ) as tmp:
            tmp.write(",".join(header) + "\n")
            for r in rows:
                tmp.write(",".join(r) + "\n")
            tmp_name = tmp.name

        self.addCleanup(lambda: os.path.exists(tmp_name) and os.unlink(tmp_name))
        return tmp_name

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

    def test_unknown_property_column_ignored(self):
        """Unknown property columns are silently ignored"""
        csv_path = self._write_csv(
            ["label", "species", "unknown_property"],
            [["300cm purpleheart", "purpleheart", "ignored_value"]],
        )

        out = StringIO()
        call_command(
            "import_entities",
            "--entity-list",
            str(self.entity_list.pk),
            csv_path,
            stdout=out,
        )

        entities = Entity.objects.filter(entity_list=self.entity_list)
        self.assertEqual(entities.count(), 1)
        self.assertEqual(entities[0].json.get("label"), "300cm purpleheart")
        self.assertEqual(entities[0].json.get("species"), "purpleheart")
        # unknown_property should not be in the entity data
        self.assertNotIn("unknown_property", entities[0].json)

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

    def test_import_entities_updates_existing(self):
        """Updates existing entity when uuid matches"""
        # Create an existing entity
        existing_entity = Entity.objects.create(
            entity_list=self.entity_list,
            json={
                "label": "old label",
                "species": "old_species",
                "circumference_cm": "100",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )

        # Import CSV with same uuid but different data
        csv_path = self._write_csv(
            ["label", "species", "circumference_cm", "uuid"],
            [
                [
                    "updated label",
                    "updated_species",
                    "400",
                    "dbee4c32-a922-451c-9df7-42f40bf78f48",
                ]
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

        # Should still have only 1 entity (updated, not duplicated)
        entities = Entity.objects.filter(entity_list=self.entity_list)
        self.assertEqual(entities.count(), 1)

        # Entity should have updated data
        updated_entity = entities[0]
        self.assertEqual(updated_entity.json.get("label"), "updated label")
        self.assertEqual(updated_entity.json.get("species"), "updated_species")
        self.assertEqual(updated_entity.json.get("circumference_cm"), "400")
        self.assertEqual(
            str(updated_entity.uuid), "dbee4c32-a922-451c-9df7-42f40bf78f48"
        )

        # Should be the same entity instance (not a new one)
        self.assertEqual(updated_entity.pk, existing_entity.pk)

    def test_import_entities_custom_label_column(self):
        """Imports entities using a custom label column name"""
        csv_path = self._write_csv(
            ["tree_name", "species", "circumference_cm"],
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
            "--label-column",
            "tree_name",
            csv_path,
            stdout=out,
        )

        entities = Entity.objects.filter(entity_list=self.entity_list).order_by("pk")
        self.assertEqual(entities.count(), 2)
        self.assertEqual(entities[0].json.get("label"), "300cm purpleheart")
        self.assertEqual(entities[0].json.get("species"), "purpleheart")
        self.assertEqual(entities[1].json.get("label"), "200cm mora")

    def test_missing_custom_label_column(self):
        """CSV without specified label column raises CommandError"""
        csv_path = self._write_csv(["species"], [["purpleheart"]])
        with self.assertRaises(CommandError):
            call_command(
                "import_entities",
                "--entity-list",
                str(self.entity_list.pk),
                "--label-column",
                "tree_name",
                csv_path,
            )

    def test_import_entities_custom_uuid_column(self):
        """Imports entities using a custom UUID column name"""
        csv_path = self._write_csv(
            ["label", "species", "circumference_cm", "entity_id"],
            [
                [
                    "300cm purpleheart",
                    "purpleheart",
                    "300",
                    "dbee4c32-a922-451c-9df7-42f40bf78f48",
                ]
            ],
        )

        out = StringIO()
        call_command(
            "import_entities",
            "--entity-list",
            str(self.entity_list.pk),
            "--uuid-column",
            "entity_id",
            csv_path,
            stdout=out,
        )

        entities = Entity.objects.filter(entity_list=self.entity_list)
        self.assertEqual(entities.count(), 1)
        self.assertEqual(entities[0].json.get("label"), "300cm purpleheart")
        self.assertEqual(str(entities[0].uuid), "dbee4c32-a922-451c-9df7-42f40bf78f48")

    def test_import_entities_custom_columns(self):
        """Imports entities using custom label and UUID columns"""
        csv_path = self._write_csv(
            ["tree_name", "species", "circumference_cm", "entity_id"],
            [
                [
                    "300cm purpleheart",
                    "purpleheart",
                    "300",
                    "dbee4c32-a922-451c-9df7-42f40bf78f48",
                ]
            ],
        )

        out = StringIO()
        call_command(
            "import_entities",
            "--entity-list",
            str(self.entity_list.pk),
            "--label-column",
            "tree_name",
            "--uuid-column",
            "entity_id",
            csv_path,
            stdout=out,
        )

        entities = Entity.objects.filter(entity_list=self.entity_list)
        self.assertEqual(entities.count(), 1)
        self.assertEqual(entities[0].json.get("label"), "300cm purpleheart")
        self.assertEqual(str(entities[0].uuid), "dbee4c32-a922-451c-9df7-42f40bf78f48")

    @patch("onadata.apps.logger.management.commands.import_entities.send_message")
    def test_audit_log_created(self, mock_send_message):
        """Creates an audit log when entities are imported"""
        csv_path = self._write_csv(
            ["label", "species", "circumference_cm"],
            [["300cm purpleheart", "purpleheart", "300"]],
        )

        out = StringIO()
        call_command(
            "import_entities",
            "--entity-list",
            str(self.entity_list.pk),
            csv_path,
            stdout=out,
        )

        mock_send_message.assert_called_once_with(
            instance_id=self.entity_list.pk,
            target_id=self.entity_list.pk,
            target_type="entitylist",
            user=None,
            message_verb="entitylist_imported",
        )
