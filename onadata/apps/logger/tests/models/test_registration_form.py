"""Tests for module onadata.apps.logger.models.registration_form"""

import json
import pytz
from datetime import datetime
from unittest.mock import patch

from django.db.utils import IntegrityError

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import RegistrationForm, EntityList, XForm, XFormVersion


class RegistrationFormTestCase(TestBase):
    """Tests for model RegistrationForm"""

    def setUp(self):
        super().setUp()

        self.mocked_now = datetime(2023, 11, 8, 13, 17, 0, tzinfo=pytz.utc)
        self.xform = self._publish_registration_form(self.user)
        self.entity_list = EntityList.objects.first()
        # Delete RegistrationForm created when form is published
        RegistrationForm.objects.all().delete()

    @patch("django.utils.timezone.now")
    def test_creation(self, mock_now):
        """We can create a RegistrationForm"""
        mock_now.return_value = self.mocked_now
        reg_form = RegistrationForm.objects.create(
            entity_list=self.entity_list,
            xform=self.xform,
            is_active=True,
        )
        self.assertEqual(RegistrationForm.objects.count(), 1)
        self.assertEqual(f"{reg_form}", f"{reg_form.xform}|trees")
        self.assertEqual(reg_form.xform, self.xform)
        self.assertEqual(reg_form.entity_list, self.entity_list)
        self.assertEqual(reg_form.date_created, self.mocked_now)
        self.assertEqual(reg_form.date_modified, self.mocked_now)
        self.assertTrue(reg_form.is_active)
        # Related names are correct
        self.assertEqual(self.entity_list.registration_forms.count(), 1)
        self.assertEqual(self.xform.registration_forms.count(), 1)

    def test_get_save_to(self):
        """Method `get_save_to` works correctly"""
        registration_form = RegistrationForm.objects.create(
            entity_list=self.entity_list,
            xform=self.xform,
        )
        self.assertEqual(
            registration_form.get_save_to(),
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
            registration_form.get_save_to("x"),
            {
                "location": "location",
                "species": "species",
                "circumference": "circumference",
            },
        )
        # Properties within grouped sections
        group_md = """
        | survey |
        |         | type        | name     | label        | save_to |
        |         | begin group | tree     | Tree         |         |
        |         | geopoint    | location | Location     | geometry|
        |         | text        | species  | Species      | species |
        |         | end group   |          |              |         |
        | settings|             |          |              |         |
        |         | form_title  | form_id  | instance_name| version |
        |         | Group       | group    | ${species}   | 2022110901|
        | entities| list_name   | label    |              |         |
        |         | trees       | ${species}|             |         |
        """
        self._publish_markdown(group_md, self.user, self.project, id_string="group")
        xform = XForm.objects.get(id_string="group")
        registration_form = RegistrationForm.objects.get(
            xform=xform, entity_list=self.entity_list
        )

        self.assertEqual(
            registration_form.get_save_to(),
            {"geometry": "location", "species": "species"},
        )

    def test_entity_list_xform_unique(self):
        """No duplicates allowed for existing entity_list and xform"""
        RegistrationForm.objects.create(
            entity_list=self.entity_list,
            xform=self.xform,
        )

        with self.assertRaises(IntegrityError):
            RegistrationForm.objects.create(
                entity_list=self.entity_list,
                xform=self.xform,
            )

    def test_optional_fields(self):
        """Defaults for optional fields correct"""
        reg_form = RegistrationForm.objects.create(
            entity_list=self.entity_list,
            xform=self.xform,
        )
        self.assertTrue(reg_form.is_active)
