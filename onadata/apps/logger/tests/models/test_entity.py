"""Tests for module onadata.apps.logger.models.entity"""

import pytz
from datetime import datetime

from onadata.apps.logger.models import Entity
from onadata.apps.logger.models.instance import Instance
from onadata.apps.main.tests.test_base import TestBase


class EntityTestCase(TestBase):
    """Tests for model Entity"""

    def setUp(self):
        super().setUp()
        # Mute signal that creates Entity when Instance is saved
        self._mute_post_save_signals([(Instance, "create_entity")])
        self.mocked_now = datetime(2023, 11, 8, 13, 17, 0, tzinfo=pytz.utc)
        self.xform = self._publish_registration_form()

    def test_creation(self):
        """We can create an Entity"""
        reg_form = self.xform.registration_forms.first()
        entity_json = {
            "formhub/uuid": "d156a2dce4c34751af57f21ef5c4e6cc",
            "geometry": "-1.286905 36.772845 0 0",
            "species": "purpleheart",
            "circumference_cm": 300,
            "meta/instanceID": "uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b",
            "meta/instanceName": "300cm purpleheart",
            "meta/entity/label": "300cm purpleheart",
            "_xform_id_string": "trees_registration",
            "_version": "2022110901",
        }
        xml = (
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
        instance = Instance.objects.create(
            xml=xml,
            user=self.user,
            xform=self.xform,
            version=self.xform.version,
        )
        instance.json = instance.get_full_dict()
        instance.save()
        instance.refresh_from_db()
        entity = Entity.objects.create(
            registration_form=reg_form,
            json={**entity_json},
            version=self.xform.version,
            xml=xml,
            instance=instance,
        )
        self.assertEqual(entity.registration_form, reg_form)
        self.assertEqual(entity.json, {**entity_json, "_id": entity.pk})
        self.assertEqual(entity.version, self.xform.version)
        self.assertEqual(entity.xml, xml)
        self.assertEqual(entity.instance, instance)
        self.assertEqual(entity.uuid, "dbee4c32-a922-451c-9df7-42f40bf78f48")
        self.assertEqual(f"{entity}", f"{entity.pk}|{reg_form}")

    def test_optional_fields(self):
        """Defaults for optional fields are correct"""
        reg_form = self.xform.registration_forms.first()
        entity = Entity.objects.create(registration_form=reg_form)
        self.assertIsNone(entity.version)
        self.assertEqual(entity.json, {"_id": entity.pk})
        self.assertIsNone(entity.instance)
        self.assertEqual(entity.xml, "")
