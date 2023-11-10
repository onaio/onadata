"""Tests for module onadata.apps.logger.models.registration_form"""

import os
import pytz
from datetime import datetime
from unittest.mock import patch

from django.db.utils import IntegrityError

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import RegistrationForm, EntityList
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
            [(DataDictionary, "create_entity_list_datadictionary")]
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

    def test_related_name(self):
        """Related names foreign keys are correct"""
        self._mute_post_save_signals(
            [(DataDictionary, "create_entity_list_datadictionary")]
        )
        self._publish_xls_file_and_set_xform(self.form_path)
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        RegistrationForm.objects.create(
            entity_list=entity_list,
            xform=self.xform,
        )
        self.assertEqual(entity_list.registration_forms.count(), 1)
        self.assertEqual(self.xform.registration_lists.count(), 1)

    def test_save_to(self):
        """Property `save_to` works correctly"""
        self._mute_post_save_signals(
            [(DataDictionary, "create_entity_list_datadictionary")]
        )
        self._publish_xls_file_and_set_xform(self.form_path)
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        save_to = {
            "geometry": "location",
            "species": "species",
            "circumference_cm": "circumference",
        }
        form = RegistrationForm.objects.create(
            entity_list=entity_list,
            xform=self.xform,
        )
        self.assertEqual(form.save_to, save_to)

    def test_entity_list_xform_unique(self):
        """No duplicates allowed for existing entity_list and xform"""
        self._mute_post_save_signals(
            [(DataDictionary, "create_entity_list_datadictionary")]
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
