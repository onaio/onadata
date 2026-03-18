"""Tests for module onadata.libs.utils.entity_utils"""

from django.db.models.signals import post_save

from onadata.apps.logger.models import (
    Entity,
    EntityHistory,
    EntityList,
    Instance,
    Project,
    RegistrationForm,
)
from onadata.apps.logger.signals import create_or_update_entity
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.entities_utils import create_or_update_entity_from_instance


class CreateUpdateEntityTestCase(TestBase):
    """Tests for create_or_update_entity_from_instance"""

    @classmethod
    def setUpClass(cls):
        # Disable signals
        post_save.disconnect(sender=Instance, dispatch_uid="create_or_update_entity")

    @classmethod
    def tearDownClass(cls):
        # Re-enable signals
        post_save.connect(
            sender=Instance,
            dispatch_uid="create_or_update_entity",
            receiver=create_or_update_entity,
        )

    def setUp(self):
        super().setUp()

        self.project = Project.objects.create(
            name="Entities", created_by=self.user, organization=self.user
        )
        self.xform = self._publish_registration_form(self.user)
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
        self.instance = Instance.objects.create(
            xml=self.xml, user=self.user, xform=self.xform
        )

    def test_entity_created(self):
        """Entity is created from a Instance"""
        self.assertEqual(Entity.objects.count(), 0)

        create_or_update_entity_from_instance(self.instance)

        self.assertEqual(Entity.objects.count(), 1)

        entity = Entity.objects.first()
        entity_list = EntityList.objects.get(name="trees", project=self.project)

        self.assertEqual(entity.entity_list, entity_list)

        expected_json = {
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "circumference_cm": 300,
            "label": "300cm purpleheart",
        }

        self.assertDictEqual(entity.json, expected_json)
        self.assertEqual(str(entity.uuid), "dbee4c32-a922-451c-9df7-42f40bf78f48")
        self.assertEqual(entity.history.count(), 1)

        entity_history = entity.history.first()
        registration_form = RegistrationForm.objects.get(xform=self.xform)

        self.assertEqual(entity_history.registration_form, registration_form)
        self.assertEqual(entity_history.instance, self.instance)
        self.assertEqual(entity_history.xml, self.instance.xml)
        self.assertDictEqual(entity_history.json, expected_json)
        self.assertEqual(entity_history.form_version, self.xform.version)
        self.assertEqual(entity_history.created_by, self.instance.user)
        self.assertEqual(
            entity_history.mutation_type, EntityHistory.MutationType.CREATE
        )

    def test_entity_updated(self):
        """Entity is updated from a Instance"""
        # Create existing entity
        entity_list = EntityList.objects.get(name="trees", project=self.project)
        entity = Entity.objects.create(
            entity_list=entity_list,
            json={
                "species": "purpleheart",
                "geometry": "-1.286905 36.772845 0 0",
                "circumference_cm": 300,
                "label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )

        # Publish update form and submit update
        update_xform = self._publish_entity_update_form(self.user)
        update_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            "<formhub><uuid>a9caf13e366b44a68f173bbb6746e3d4</uuid></formhub>"
            "<tree>dbee4c32-a922-451c-9df7-42f40bf78f48</tree>"
            "<circumference>30</circumference>"
            "<today>2024-05-28</today>"
            "<meta>"
            "<instanceID>uuid:45d27780-48fd-4035-8655-9332649385bd</instanceID>"
            "<instanceName>30cm dbee4c32-a922-451c-9df7-42f40bf78f48</instanceName>"
            '<entity dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48"'
            ' update="1" baseVersion=""/>'
            "</meta>"
            "</data>"
        )
        update_instance = Instance.objects.create(
            xml=update_xml, user=self.user, xform=update_xform
        )

        create_or_update_entity_from_instance(update_instance)

        # No new Entity created
        self.assertEqual(Entity.objects.count(), 1)

        entity.refresh_from_db()
        expected_json = {
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "circumference_cm": 30,
            "latest_visit": "2024-05-28",
            "label": "300cm purpleheart",
        }

        self.assertDictEqual(entity.json, expected_json)

        entity_history = entity.history.first()
        registration_form = RegistrationForm.objects.get(xform=update_xform)

        self.assertEqual(entity_history.registration_form, registration_form)
        self.assertEqual(entity_history.instance, update_instance)
        self.assertEqual(entity_history.xml, update_xml)
        self.assertDictEqual(entity_history.json, expected_json)
        self.assertEqual(entity_history.form_version, update_xform.version)
        self.assertEqual(entity_history.created_by, update_instance.user)
        self.assertEqual(
            entity_history.mutation_type, EntityHistory.MutationType.UPDATE
        )

    def test_entity_created_if_duplicate_other_project(self):
        """Entity is created if duplicate uuid belongs to different project"""
        # Simulate an existing Entity same uuid, different project
        project = Project.objects.create(
            name="Project B", created_by=self.user, organization=self.user
        )
        self._publish_registration_form(self.user, project)
        entity_list = EntityList.objects.get(name="trees", project=project)
        Entity.objects.create(
            entity_list=entity_list,
            json={
                "species": "purpleheart",
                "geometry": "-1.286905 36.772845 0 0",
                "circumference_cm": 30,
                "label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )

        self.assertEqual(Entity.objects.count(), 1)

        create_or_update_entity_from_instance(self.instance)

        self.assertEqual(Entity.objects.count(), 2)

    def test_entity_creation_rejected_if_duplicate_same_project(self):
        """Entity is rejected if duplicate uuid belongs to same project"""
        # Simulate an existing Entity same uuid, same project
        entity_list = EntityList.objects.get(name="trees", project=self.project)
        Entity.objects.create(
            entity_list=entity_list,
            json={
                "species": "purpleheart",
                "geometry": "-1.286905 36.772845 0 0",
                "circumference_cm": 30,
                "label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )

        self.assertEqual(Entity.objects.count(), 1)

        create_or_update_entity_from_instance(self.instance)

        self.assertEqual(Entity.objects.count(), 1)

    def test_entity_updated_if_duplicate_other_project(self):
        """Entity is updated even if duplicate uuid exists in another project"""
        entity_list = EntityList.objects.get(name="trees", project=self.project)
        entity = Entity.objects.create(
            entity_list=entity_list,
            json={
                "species": "purpleheart",
                "geometry": "-1.286905 36.772845 0 0",
                "circumference_cm": 300,
                "label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )
        # Create duplicate entity in a different project
        other_project = Project.objects.create(
            name="Project B", created_by=self.user, organization=self.user
        )
        self._publish_registration_form(self.user, other_project)
        other_entity_list = EntityList.objects.get(name="trees", project=other_project)
        other_entity = Entity.objects.create(
            entity_list=other_entity_list,
            json={
                "species": "mora",
                "geometry": "-1.0 36.0 0 0",
                "circumference_cm": 100,
                "label": "100cm mora",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )

        self.assertEqual(Entity.objects.count(), 2)

        # Publish update form in current project and submit update
        update_xform = self._publish_entity_update_form(self.user)
        update_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="trees_update" version="2024050801">'
            "<formhub><uuid>a9caf13e366b44a68f173bbb6746e3d4</uuid></formhub>"
            "<tree>dbee4c32-a922-451c-9df7-42f40bf78f48</tree>"
            "<circumference>30</circumference>"
            "<today>2024-05-28</today>"
            "<meta>"
            "<instanceID>uuid:45d27780-48fd-4035-8655-9332649385bd</instanceID>"
            "<instanceName>30cm dbee4c32-a922-451c-9df7-42f40bf78f48</instanceName>"
            '<entity dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48"'
            ' update="1" baseVersion=""/>'
            "</meta>"
            "</data>"
        )
        update_instance = Instance.objects.create(
            xml=update_xml, user=self.user, xform=update_xform
        )

        create_or_update_entity_from_instance(update_instance)

        # No new Entity created
        self.assertEqual(Entity.objects.count(), 2)

        # Entity in current project is updated
        entity.refresh_from_db()
        self.assertEqual(entity.json["circumference_cm"], 30)
        self.assertEqual(entity.json["latest_visit"], "2024-05-28")
        # Original properties preserved
        self.assertEqual(entity.json["species"], "purpleheart")
        self.assertEqual(entity.json["geometry"], "-1.286905 36.772845 0 0")

        # Entity in other project is NOT updated
        other_entity.refresh_from_db()
        self.assertEqual(other_entity.json["circumference_cm"], 100)
        self.assertNotIn("latest_visit", other_entity.json)

        # EntityHistory created with correct mutation type
        entity_history = entity.history.first()
        registration_form = RegistrationForm.objects.get(xform=update_xform)
        self.assertEqual(entity_history.registration_form, registration_form)
        self.assertEqual(entity_history.instance, update_instance)
        self.assertEqual(
            entity_history.mutation_type, EntityHistory.MutationType.UPDATE
        )
