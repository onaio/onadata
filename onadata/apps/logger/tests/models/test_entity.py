"""Tests for module onadata.apps.logger.models.entity"""
import os
import pytz
from datetime import datetime

from onadata.apps.logger.models import Entity
from onadata.apps.main.tests.test_base import TestBase


class EntityTestCase(TestBase):
    """Tests for model Entity"""

    def setUp(self):
        super().setUp()

        self.mocked_now = datetime(2023, 11, 8, 13, 17, 0, tzinfo=pytz.utc)
        fixture_dir = os.path.join(self.this_directory, "fixtures", "entities")
        form_path = os.path.join(fixture_dir, "trees_registration.xlsx")
        self._publish_xls_file_and_set_xform(form_path)

    def test_creation(self):
        """We can create an Entity"""
        reg_form = self.xform.registration_lists.first()
        entity_json = {"foo": "very_foo"}
        entity = Entity.objects.create(
            registration_form=reg_form,
            json=entity_json,
            version="x",
        )
        self.assertEqual(entity.registration_form, reg_form)
        self.assertEqual(entity.json, entity_json)
        self.assertEqual(entity.version, "x")
        self.assertEqual(f"{entity}", f"{entity.pk}|{reg_form}")

    def test_optional_fields(self):
        """Defaults for optional fields are correct"""
        reg_form = self.xform.registration_lists.first()
        entity_json = {"foo": "very_foo"}
        entity = Entity.objects.create(registration_form=reg_form, json=entity_json)
        self.assertIsNone(entity.version)
