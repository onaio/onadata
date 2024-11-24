"""Tests for module onadata.apps.logger.models.entity"""

import uuid
import pytz
from datetime import datetime
from unittest.mock import patch

from django.db.utils import IntegrityError
from django.utils import timezone

from onadata.apps.logger.models import (
    Entity,
    EntityHistory,
    EntityList,
    Instance,
    SurveyType,
)
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.user_auth import get_user_default_project


class EntityTestCase(TestBase):
    """Tests for model Entity"""

    def setUp(self):
        super().setUp()

        self.mocked_now = datetime(2023, 11, 8, 13, 17, 0, tzinfo=pytz.utc)
        self.project = get_user_default_project(self.user)
        self.entity_list = EntityList.objects.create(name="trees", project=self.project)

    @patch("django.utils.timezone.now")
    def test_creation(self, mock_now):
        """We can create an Entity"""
        mock_now.return_value = self.mocked_now
        entity_json = {
            "geometry": "-1.286905 36.772845 0 0",
            "circumference_cm": 300,
            "label": "300cm purpleheart",
        }
        entity_uuid = "dbee4c32-a922-451c-9df7-42f40bf78f48"
        entity = Entity.objects.create(
            entity_list=self.entity_list,
            json=entity_json,
            uuid=entity_uuid,
        )
        self.assertEqual(entity.entity_list, self.entity_list)
        self.assertEqual(entity.json, entity_json)
        self.assertEqual(entity.uuid, entity_uuid)
        self.assertEqual(f"{entity}", f"{entity.pk}|{self.entity_list}")
        self.assertEqual(entity.date_created, self.mocked_now)

    def test_optional_fields(self):
        """Defaults for optional fields are correct"""
        entity = Entity.objects.create(entity_list=self.entity_list)
        self.assertIsNone(entity.deleted_at)
        self.assertIsNone(entity.deleted_by)
        self.assertEqual(entity.json, {})
        self.assertIsInstance(entity.uuid, uuid.UUID)

    @patch("onadata.apps.logger.tasks.dec_elist_num_entities_async.delay")
    @patch("django.utils.timezone.now")
    def test_soft_delete(self, mock_now, mock_dec):
        """Soft delete works"""
        mock_now.return_value = self.mocked_now
        entity = Entity.objects.create(entity_list=self.entity_list)
        self.entity_list.refresh_from_db()

        self.assertIsNone(entity.deleted_at)
        self.assertIsNone(entity.deleted_by)

        entity.soft_delete(self.user)
        self.entity_list.refresh_from_db()
        entity.refresh_from_db()

        self.assertEqual(self.entity_list.last_entity_update_time, self.mocked_now)
        self.assertEqual(entity.deleted_at, self.mocked_now)
        self.assertEqual(entity.deleted_at, self.mocked_now)
        mock_dec.assert_called_once_with(self.entity_list.pk)

        # Soft deleted item cannot be soft deleted again
        deleted_at = timezone.now()
        entity2 = Entity.objects.create(
            entity_list=self.entity_list, deleted_at=deleted_at
        )
        entity2.soft_delete(self.user)
        entity2.refresh_from_db()
        # deleted_at should not remain unchanged
        self.assertEqual(entity2.deleted_at, deleted_at)

        # deleted_by is optional
        entity3 = Entity.objects.create(entity_list=self.entity_list)
        entity3.soft_delete()
        entity2.refresh_from_db()

        self.assertEqual(entity3.deleted_at, self.mocked_now)
        self.assertIsNone(entity3.deleted_by)

    @patch("onadata.apps.logger.tasks.dec_elist_num_entities_async.delay")
    def test_hard_delete(self, mock_dec):
        """Hard deleting updates dataset info"""
        entity = Entity.objects.create(entity_list=self.entity_list)
        self.entity_list.refresh_from_db()
        old_last_entity_update_time = self.entity_list.last_entity_update_time

        entity.delete()
        self.entity_list.refresh_from_db()
        new_last_entity_update_time = self.entity_list.last_entity_update_time

        self.assertTrue(old_last_entity_update_time < new_last_entity_update_time)
        mock_dec.assert_called_once_with(self.entity_list.pk)

    def test_entity_list_uuid_unique(self):
        """`entity_list` and `uuid` are unique together"""
        entity_uuid = "dbee4c32-a922-451c-9df7-42f40bf78f48"
        Entity.objects.create(
            entity_list=self.entity_list,
            uuid=entity_uuid,
        )

        with self.assertRaises(IntegrityError):
            Entity.objects.create(
                entity_list=self.entity_list,
                uuid=entity_uuid,
            )


class EntityHistoryTestCase(TestBase):
    """Tests for model EntityHistory"""

    def setUp(self):
        super().setUp()
        self.mocked_now = datetime(2023, 11, 8, 13, 17, 0, tzinfo=pytz.utc)
        self.xform = self._publish_registration_form(self.user)
        self.entity_list = EntityList.objects.first()
        self.entity = Entity.objects.create(entity_list=self.entity_list)
        self.xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_registration" version="2022110901">'
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
            "label": "300cm purpleheart",
        }
        survey_type = SurveyType.objects.create(slug="slug-foo")
        instance = Instance(xform=self.xform, xml=self.xml, survey_type=survey_type)
        # We use bulk_create to avoid calling create_entity signal
        Instance.objects.bulk_create([instance])
        instance = Instance.objects.first()
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
