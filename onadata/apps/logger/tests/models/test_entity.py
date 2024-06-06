"""Tests for module onadata.apps.logger.models.entity"""

import pytz
from datetime import datetime
from unittest.mock import patch

from onadata.apps.logger.models import Entity, EntityHistory, EntityList, Instance
from onadata.apps.main.tests.test_base import TestBase


class EntityTestCase(TestBase):
    """Tests for model Entity"""

    def setUp(self):
        super().setUp()
        self.mocked_now = datetime(2023, 11, 8, 13, 17, 0, tzinfo=pytz.utc)
        self.entity_list = EntityList.objects.first()

    @patch("django.utils.timezone.now")
    def test_creation(self, mock_now):
        """We can create an Entity"""
        mock_now.return_value = self.mocked_now
        entity_json = {
            "geometry": "-1.286905 36.772845 0 0",
            "circumference_cm": 300,
            "meta/entity/label": "300cm purpleheart",
        }
        entity = Entity.objects.create(
            entity_list=self.entity_list,
            json=entity_json,
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )
        self.assertEqual(entity.entity_list, self.entity_list)
        self.assertEqual(entity.json, {"id": entity.pk, **entity_json})
        self.assertEqual(entity.uuid, "dbee4c32-a922-451c-9df7-42f40bf78f48")
        self.assertEqual(f"{entity}", f"{entity.pk}|{self.entity_list}")
        self.assertEqual(entity.date_created, self.mocked_now)

    def test_optional_fields(self):
        """Defaults for optional fields are correct"""
        entity = Entity.objects.create(entity_list=self.entity_list)
        self.assertIsNone(entity.deleted_at)
        self.assertIsNone(entity.deleted_by)
        self.assertEqual(entity.json, {"id": entity.pk})
        self.assertEqual(entity.uuid, "")


class EntityHistoryTestCase(TestBase):
    """Tests for model EntityHistory"""

    def setUp(self):
        super().setUp()
        self._mute_post_save_signals([(Instance, "create_entity")])
        self.mocked_now = datetime(2023, 11, 8, 13, 17, 0, tzinfo=pytz.utc)
        self.xform = self._publish_registration_form(self.user)
        self.entity_list = EntityList.objects.first()
        self.entity = Entity.objects.create(entity_list=self.entity_list)
        self.xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_registration" version="202311070702">'
            "<formhub><uuid>d156a2dce4c34751af57f21ef5c4e6cc</uuid></formhub>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>purpleheart</species>"
            "<circumference>300</circumference>"
            "<intake_notes />"
            "<meta>"
            "<instanceID>uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b</instanceID>"
            "<instanceName>300cm purpleheart</instanceName>"
            '<entity create="1" dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48">'
            "<label>300cm purpleheart</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )

    @patch("django.utils.timezone.now")
    def test_creation(self, mock_now):
        """We can create an EntityHistory"""
        mock_now.return_value = self.mocked_now
        registration_form = self.xform.registration_forms.first()
        entity_json = {
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "circumference_cm": 300,
            "meta/entity/label": "300cm purpleheart",
        }
        instance = Instance.objects.create(xform=self.xform, xml=self.xml)
        history = EntityHistory.objects.create(
            entity=self.entity,
            registration_form=registration_form,
            instance=instance,
            xml=self.xml,
            json=entity_json,
            form_version=self.xform.version,
            created_by=self.user,
        )
        self.assertEqual(history.entity, self.entity)
        self.assertEqual(history.registration_form, registration_form)
        self.assertEqual(history.instance, instance)
        self.assertEqual(history.xml, self.xml)
        self.assertEqual(history.form_version, self.xform.version)
        self.assertEqual(history.created_by, self.user)
        self.assertEqual(history.date_created, self.mocked_now)

    def test_optional_fields(self):
        """Default for optional fields are correct"""
        history = EntityHistory.objects.create(entity=self.entity)
        self.assertEqual(history.entity, self.entity)
        self.assertIsNone(history.registration_form)
        self.assertIsNone(history.instance)
        self.assertIsNone(history.xml)
        self.assertIsNone(history.form_version)
        self.assertIsNone(history.created_by)
