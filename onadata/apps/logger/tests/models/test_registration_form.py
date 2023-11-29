"""Tests for module onadata.apps.logger.models.registration_form"""

import json
import os
import pytz
from datetime import datetime
from unittest.mock import patch

from django.db.utils import IntegrityError

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import RegistrationForm, EntityList, XFormVersion
from onadata.apps.viewer.models import DataDictionary


class RegistrationFormTestCase(TestBase):
    """Tests for model RegistrationForm"""

    def setUp(self):
        super().setUp()

        self.mocked_now = datetime(2023, 11, 8, 13, 17, 0, tzinfo=pytz.utc)
        fixture_dir = os.path.join(self.this_directory, "fixtures", "entities")
        self.form_path = os.path.join(fixture_dir, "trees_registration.xlsx")

    @patch("django.utils.timezone.now")
    def test_creation(self, mock_now):
        """We can create a RegistrationForm"""
        mock_now.return_value = self.mocked_now
        self._mute_post_save_signals(
            [(DataDictionary, "create_registration_form_datadictionary")]
        )
        self._publish_xls_file_and_set_xform(self.form_path)
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        reg_form = RegistrationForm.objects.create(
            entity_list=entity_list,
            xform=self.xform,
        )
        self.assertEqual(RegistrationForm.objects.count(), 1)
        self.assertEqual(f"{reg_form}", f"{reg_form.xform}|trees")
        self.assertEqual(reg_form.xform, self.xform)
        self.assertEqual(reg_form.entity_list, entity_list)
        self.assertEqual(reg_form.created_at, self.mocked_now)
        self.assertEqual(reg_form.updated_at, self.mocked_now)
        # Related names are correct
        self.assertEqual(entity_list.registration_forms.count(), 1)
        self.assertEqual(self.xform.registration_lists.count(), 1)

    def test_get_save_to(self):
        """Method `get_save_to` works correctly"""
        self._mute_post_save_signals(
            [(DataDictionary, "create_registration_form_datadictionary")]
        )
        self._publish_xls_file_and_set_xform(self.form_path)
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        form = RegistrationForm.objects.create(
            entity_list=entity_list,
            xform=self.xform,
        )
        self.assertEqual(
            form.get_save_to(),
            {
                "geometry": "location",
                "species": "species",
                "circumference_cm": "circumference",
            },
        )
        # Passing version argument works
        x_version_json = {
            "name": "data",
            "type": "survey",
            "title": "Trees registration",
            "version": "x",
            "children": [
                {
                    "bind": {"required": "yes", "entities:saveto": "location"},
                    "name": "location",
                    "type": "geopoint",
                    "label": "Tree location",
                },
                {
                    "bind": {"required": "yes", "entities:saveto": "species"},
                    "name": "species",
                    "type": "select one",
                    "label": "Tree species",
                    "children": [
                        {"name": "wallaba", "label": "Wallaba"},
                        {"name": "mora", "label": "Mora"},
                        {"name": "purpleheart", "label": "Purpleheart"},
                        {"name": "greenheart", "label": "Greenheart"},
                    ],
                    "list_name": "species",
                },
                {
                    "bind": {"required": "yes", "entities:saveto": "circumference"},
                    "name": "circumference",
                    "type": "integer",
                    "label": "Tree circumference in cm",
                },
                {"name": "intake_notes", "type": "text", "label": "Intake notes"},
                {
                    "name": "meta",
                    "type": "group",
                    "control": {"bodyless": "true"},
                    "children": [
                        {
                            "bind": {"readonly": "true()", "jr:preload": "uid"},
                            "name": "instanceID",
                            "type": "calculate",
                        },
                        {
                            "bind": {
                                "calculate": 'concat(${circumference}, "cm ", ${species})'
                            },
                            "name": "instanceName",
                            "type": "calculate",
                        },
                        {
                            "name": "entity",
                            "type": "entity",
                            "parameters": {
                                "label": 'concat(${circumference}, "cm ", ${species})',
                                "create": "1",
                                "dataset": "trees",
                            },
                        },
                    ],
                },
            ],
            "id_string": "trees_registration",
            "sms_keyword": "trees_registration",
            "entity_related": "true",
            "default_language": "default",
        }
        XFormVersion.objects.create(
            xform=self.xform,
            version="x",
            xls=self.xform.xls,
            xml=self.xform.xml,
            json=json.dumps(x_version_json),
        )
        self.assertEqual(
            form.get_save_to("x"),
            {
                "location": "location",
                "species": "species",
                "circumference": "circumference",
            },
        )

    def test_entity_list_xform_unique(self):
        """No duplicates allowed for existing entity_list and xform"""
        self._mute_post_save_signals(
            [(DataDictionary, "create_registration_form_datadictionary")]
        )
        self._publish_xls_file_and_set_xform(self.form_path)
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        RegistrationForm.objects.create(
            entity_list=entity_list,
            xform=self.xform,
        )

        with self.assertRaises(IntegrityError):
            RegistrationForm.objects.create(
                entity_list=entity_list,
                xform=self.xform,
            )
