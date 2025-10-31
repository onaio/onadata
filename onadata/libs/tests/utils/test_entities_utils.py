# -*- coding: utf-8 -*-
"""
Test entities_utils utility functions.
"""

from datetime import datetime, timedelta
from datetime import timezone as dtz
from io import StringIO
from unittest.mock import call, patch

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from onadata.apps.logger.models import (
    Entity,
    EntityHistory,
    EntityList,
    Instance,
    RegistrationForm,
    SurveyType,
    XForm,
)
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.exceptions import CSVImportError
from onadata.libs.utils.entities_utils import (
    adjust_elist_num_entities,
    commit_cached_elist_num_entities,
    create_entity_from_instance,
    import_entities_from_csv,
    update_entity_from_instance,
)
from onadata.libs.utils.user_auth import get_user_default_project


class CreateEntityFromInstanceTestCase(TestBase):
    """Tests for method `create_entity_from_instance`"""

    def setUp(self):
        super().setUp()
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
        self.survey_type = SurveyType.objects.create(slug="slug-foo")
        instance = Instance(
            xform=self.xform,
            xml=self.xml,
            version=self.xform.version,
            survey_type=self.survey_type,
        )
        # We use bulk_create to avoid calling create_entity signal
        Instance.objects.bulk_create([instance])
        self.instance = Instance.objects.first()
        self.registration_form = RegistrationForm.objects.first()
        self.entity_list = EntityList.objects.get(name="trees")

    def test_entity_created(self):
        """Entity is created successfully"""
        create_entity_from_instance(self.instance, self.registration_form)

        self.assertEqual(Entity.objects.count(), 1)

        entity = Entity.objects.first()
        entity_list = self.registration_form.entity_list
        entity_list.refresh_from_db()

        self.assertEqual(entity.entity_list, entity_list)

        expected_json = {
            "geometry": "-1.286905 36.772845 0 0",
            "species": "purpleheart",
            "circumference_cm": 300,
            "label": "300cm purpleheart",
        }

        self.assertCountEqual(entity.json, expected_json)
        self.assertEqual(str(entity.uuid), "dbee4c32-a922-451c-9df7-42f40bf78f48")

        self.assertEqual(cache.get(f"elist-num-entities-{entity_list.pk}"), 1)
        self.assertEqual(entity_list.last_entity_update_time, entity.date_modified)
        self.assertEqual(entity.history.count(), 1)

        entity_history = entity.history.first()

        self.assertEqual(entity_history.registration_form, self.registration_form)
        self.assertEqual(entity_history.instance, self.instance)
        self.assertEqual(entity_history.xml, self.instance.xml)
        self.assertEqual(entity_history.json, expected_json)
        self.assertEqual(entity_history.form_version, self.xform.version)
        self.assertEqual(entity_history.created_by, self.instance.user)
        self.assertEqual(entity_history.mutation_type, "create")

    def test_grouped_section(self):
        """Entity properties within grouped section"""
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
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx='
            '"http://openrosa.org/xforms" id="group" version="2022110901">'
            "<formhub><uuid>9833e23e6c6147298e0ae2d691dc1e6f</uuid></formhub>"
            "<tree>"
            "<location>-1.286905 36.772845 0 0</location>"
            "<species>purpleheart</species>"
            "</tree>"
            "<meta>"
            "<instanceID>uuid:b817c598-a215-4fa9-ba78-a7c738bd1f91</instanceID>"
            "<instanceName>purpleheart</instanceName>"
            '<entity create="1" dataset="trees" id="47e335da-46ce-4151-9898-7ed1d54778c6">'
            "<label>purpleheart</label>"
            "</entity>"
            "</meta>"
            "</data>"
        )
        instance = Instance(
            xform=xform,
            xml=xml,
            version=xform.version,
            survey_type=self.survey_type,
        )
        # We use bulk_create to avoid calling create_entity signal
        Instance.objects.bulk_create([instance])
        instance = Instance.objects.order_by("pk").last()
        registration_form = RegistrationForm.objects.get(
            xform=xform, entity_list=self.entity_list
        )
        create_entity_from_instance(instance, registration_form)
        entity = Entity.objects.first()
        expected_json = {
            "geometry": "-1.286905 36.772845 0 0",
            "species": "purpleheart",
            "label": "purpleheart",
        }

        self.assertEqual(Entity.objects.count(), 1)
        self.assertCountEqual(entity.json, expected_json)


class UpdateEntityFromInstanceTestCase(TestBase):
    """Tests for method `update_entity_from_instance`"""

    def setUp(self):
        super().setUp()

        self._simulate_existing_entity()
        self.xform = self._publish_entity_update_form(self.user)
        self.xml = (
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
            '<entity dataset="trees" id="dbee4c32-a922-451c-9df7-42f40bf78f48" update="1" baseVersion=""/>'
            "</meta>"
            "</data>"
        )
        self.instance = Instance.objects.create(
            xml=self.xml, user=self.user, xform=self.xform
        )
        self.registration_form = RegistrationForm.objects.filter(
            xform=self.xform
        ).first()

    def test_entity_updated(self):
        """Entity is updated successfully"""
        update_entity_from_instance(
            self.entity.uuid, self.instance, self.registration_form
        )
        # No new Entity created
        self.assertEqual(Entity.objects.count(), 1)

        entity = Entity.objects.first()
        expected_json = {
            "species": "purpleheart",
            "geometry": "-1.286905 36.772845 0 0",
            "latest_visit": "2024-05-28",
            "circumference_cm": 30,
            "label": "300cm purpleheart",
        }

        self.assertDictEqual(entity.json, expected_json)

        entity_history = entity.history.first()

        self.assertEqual(entity_history.registration_form, self.registration_form)
        self.assertEqual(entity_history.instance, self.instance)
        self.assertEqual(entity_history.xml, self.xml)
        self.assertDictEqual(entity_history.json, expected_json)
        self.assertEqual(entity_history.form_version, self.xform.version)
        self.assertEqual(entity_history.created_by, self.instance.user)
        self.assertEqual(entity_history.mutation_type, "update")
        # New property is part of EntityList properties
        self.assertTrue("latest_visit" in entity.entity_list.properties)


class EntityListNumEntitiesBase(TestBase):
    def setUp(self):
        super().setUp()

        self.project = get_user_default_project(self.user)
        self.entity_list = EntityList.objects.create(
            name="trees", project=self.project, num_entities=10
        )
        self.ids_key = "elist-num-entities-ids"
        self.lock_key = f"{self.ids_key}-lock"
        self.counter_key_prefix = "elist-num-entities-"
        self.counter_key = f"{self.counter_key_prefix}{self.entity_list.pk}"
        self.created_at_key = "elist-num-entities-ids-created-at"

    def tearDown(self) -> None:
        super().tearDown()

        cache.clear()


class IncEListNumEntitiesTestCase(EntityListNumEntitiesBase):
    """Tests for method `inc_elist_num_entities`"""

    def test_cache_locked(self):
        """Database counter is incremented if cache is locked"""
        cache.set(self.lock_key, "true")
        cache.set(self.counter_key, 3)
        adjust_elist_num_entities(self.entity_list, delta=1)
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 11)
        # Cached counter should not be updated
        self.assertEqual(cache.get(self.counter_key), 3)

    @patch("django.utils.timezone.now")
    def test_cache_unlocked(self, mock_now):
        """Cache counter is incremented if cache is unlocked"""
        mocked_now = datetime(2024, 7, 26, 12, 45, 0, tzinfo=dtz.utc)
        mock_now.return_value = mocked_now

        self.assertIsNone(cache.get(self.counter_key))
        self.assertIsNone(cache.get(self.ids_key))
        self.assertIsNone(cache.get(self.created_at_key))

        adjust_elist_num_entities(self.entity_list, delta=1)

        self.assertEqual(cache.get(self.counter_key), 1)
        self.assertEqual(cache.get(self.ids_key), {self.entity_list.pk})
        self.assertEqual(cache.get(self.created_at_key), mocked_now)
        self.entity_list.refresh_from_db()
        # Database counter should not be updated
        self.assertEqual(self.entity_list.num_entities, 10)
        # New EntityList
        vaccine = EntityList.objects.create(name="vaccine", project=self.project)
        adjust_elist_num_entities(vaccine, delta=1)

        self.assertEqual(cache.get(f"{self.counter_key_prefix}{vaccine.pk}"), 1)
        self.assertEqual(cache.get(self.ids_key), {self.entity_list.pk, vaccine.pk})
        vaccine.refresh_from_db()
        self.assertEqual(vaccine.num_entities, 0)

        # Database counter incremented if cache inacessible
        with patch(
            "onadata.libs.utils.model_tools._increment_cached_counter"
        ) as mock_inc:
            with patch("onadata.libs.utils.model_tools.logger.exception") as mock_exc:
                mock_inc.side_effect = ConnectionError
                cache.set(self.counter_key, 3)
                adjust_elist_num_entities(self.entity_list, delta=1)
                self.entity_list.refresh_from_db()

                self.assertEqual(cache.get(self.counter_key), 3)
                self.assertEqual(self.entity_list.num_entities, 11)
                mock_exc.assert_called_once()

    @patch("django.utils.timezone.now")
    @patch.object(cache, "set")
    @patch.object(cache, "add")
    def test_cache_no_expire(self, mock_cache_add, mock_cache_set, mock_now):
        """Cached counter does not expire

        Clean up should be done periodically such as in a background task
        """
        mocked_now = datetime(2024, 7, 26, 12, 45, 0, tzinfo=dtz.utc)
        mock_now.return_value = mocked_now
        adjust_elist_num_entities(self.entity_list, delta=1)

        # Timeout should be `None`
        self.assertTrue(
            call(self.counter_key, 1, timeout=None) in mock_cache_add.call_args_list
        )
        self.assertTrue(
            call(self.created_at_key, mocked_now, timeout=None)
            in mock_cache_add.call_args_list
        )
        mock_cache_set.assert_called_once_with(
            self.ids_key, {self.entity_list.pk}, None
        )

    def test_time_cache_set_once(self):
        """The cached time of creation is set once"""
        now = timezone.now()
        cache.set(self.created_at_key, now)

        adjust_elist_num_entities(self.entity_list, delta=1)
        # Cache value is not overridden
        self.assertEqual(cache.get(self.created_at_key), now)

    @override_settings(COUNTER_COMMIT_FAILOVER_TIMEOUT=3)
    @patch("onadata.libs.utils.model_tools.report_exception")
    def test_failover(self, mock_report_exc):
        """Failover is executed if commit timeout threshold exceeded"""
        cache_created_at = timezone.now() - timedelta(minutes=10)
        cache.set(self.counter_key, 3)
        cache.set(self.created_at_key, cache_created_at)
        cache.set(self.ids_key, {self.entity_list.pk})

        adjust_elist_num_entities(self.entity_list, delta=1)
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 14)
        self.assertIsNone(cache.get(self.counter_key))
        self.assertIsNone(cache.get(self.ids_key))
        self.assertIsNone(cache.get(self.created_at_key))
        subject = "Periodic task not running"
        task_name = "onadata.apps.logger.tasks.commit_cached_elist_num_entities_async"
        msg = (
            f"The failover has been executed because task {task_name} "
            "is not configured or has malfunctioned"
        )
        mock_report_exc.assert_called_once_with(subject, msg)
        self.assertEqual(cache.get("elist-failover-report-sent"), "sent")

    @override_settings(COUNTER_COMMIT_FAILOVER_TIMEOUT=3)
    @patch("onadata.libs.utils.model_tools.report_exception")
    def test_failover_report_cache_hit(self, mock_report_exc):
        """Report exception not sent if cache `elist-failover-report-sent` set"""
        cache.set("elist-failover-report-sent", "sent")
        cache_created_at = timezone.now() - timedelta(minutes=10)
        cache.set(self.counter_key, 3)
        cache.set(self.created_at_key, cache_created_at)
        cache.set(self.ids_key, {self.entity_list.pk})

        adjust_elist_num_entities(self.entity_list, delta=1)
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 14)
        self.assertIsNone(cache.get(self.counter_key))
        self.assertIsNone(cache.get(self.ids_key))
        self.assertIsNone(cache.get(self.created_at_key))
        mock_report_exc.assert_not_called()


class DecEListNumEntitiesTestCase(EntityListNumEntitiesBase):
    """Tests for method `dec_elist_num_entities`"""

    def test_cache_locked(self):
        """Database counter is decremented if cache is locked"""
        counter_key = f"{self.counter_key_prefix}{self.entity_list.pk}"
        cache.set(self.lock_key, "true")
        cache.set(counter_key, 3)
        adjust_elist_num_entities(self.entity_list, delta=-1)
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 9)
        # Cached counter should not be updated
        self.assertEqual(cache.get(counter_key), 3)

    def test_cache_unlocked(self):
        """Cache counter is decremented if cache is unlocked"""
        counter_key = f"{self.counter_key_prefix}{self.entity_list.pk}"
        cache.set(counter_key, 3)
        adjust_elist_num_entities(self.entity_list, delta=-1)

        self.assertEqual(cache.get(counter_key), 2)
        self.entity_list.refresh_from_db()
        # Database counter should not be updated
        self.assertEqual(self.entity_list.num_entities, 10)

        # Database counter is decremented if cache missing
        cache.delete(counter_key)
        adjust_elist_num_entities(self.entity_list, delta=-1)
        self.entity_list.refresh_from_db()
        self.assertEqual(self.entity_list.num_entities, 9)

        # Database counter is decremented if cache inaccesible
        with patch(
            "onadata.libs.utils.model_tools._decrement_cached_counter"
        ) as mock_dec:
            with patch("onadata.libs.utils.model_tools.logger.exception") as mock_exc:
                mock_dec.side_effect = ConnectionError
                cache.set(counter_key, 3)
                adjust_elist_num_entities(self.entity_list, delta=-1)
                self.entity_list.refresh_from_db()

                self.assertEqual(cache.get(counter_key), 3)
                self.assertEqual(self.entity_list.num_entities, 8)
                mock_exc.assert_called_once()


class CommitCachedEListNumEntitiesTestCase(EntityListNumEntitiesBase):
    """Tests for method `commit_cached_elist_num_entities`"""

    def test_counter_commited(self):
        """Cached counter is commited in the database"""
        cache.set(self.ids_key, {self.entity_list.pk})
        cache.set(self.counter_key, 3)
        cache.set(self.created_at_key, timezone.now())
        commit_cached_elist_num_entities()
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 13)
        self.assertIsNone(cache.get(self.ids_key))
        self.assertIsNone(cache.get(self.counter_key))
        self.assertIsNone(cache.get(self.created_at_key))

    def test_cache_empty(self):
        """Empty cache is handled appropriately"""
        commit_cached_elist_num_entities()
        self.entity_list.refresh_from_db()
        self.assertEqual(self.entity_list.num_entities, 10)

    def test_lock_already_acquired(self):
        """Commit unsuccessful if lock is already acquired"""
        cache.set(self.lock_key, "true")
        cache.set(self.ids_key, {self.entity_list.pk})
        cache.set(self.counter_key, 3)
        cache.set(self.created_at_key, timezone.now())
        commit_cached_elist_num_entities()
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 10)
        self.assertIsNotNone(cache.get(self.lock_key))
        self.assertIsNotNone(cache.get(self.ids_key))
        self.assertIsNotNone(cache.get(self.counter_key))
        self.assertIsNotNone(cache.get(self.created_at_key))


class ImportEntitiesFromCSVTestCase(TestBase):
    """Tests for method `import_entities_from_csv`"""

    def setUp(self):
        super().setUp()

        # Create a registration form which will create an EntityList with properties
        self._publish_registration_form(self.user)
        self.entity_list = EntityList.objects.get(name="trees", project=self.project)

    def _create_csv_file(self, content):
        """Helper to create a CSV file from content string"""
        return StringIO(content)

    def test_import_success(self):
        """Successfully imports entities from CSV with valid data"""
        csv_content = (
            "label,species,circumference_cm\n"
            "300cm purpleheart,purpleheart,300\n"
            "200cm mora,mora,200\n"
        )
        csv_file = self._create_csv_file(csv_content)

        for row_result in import_entities_from_csv(
            self.entity_list,
            csv_file,
            label_column="label",
            user=self.user,
            dry_run=False,
        ):
            for row_result.index in [2, 3]:
                self.assertEqual(row_result.status, "created")
                self.assertIsNotNone(row_result)

        entities = Entity.objects.filter(entity_list=self.entity_list).order_by("pk")

        self.assertEqual(entities.count(), 2)
        self.assertEqual(entities[0].json.get("label"), "300cm purpleheart")
        self.assertEqual(entities[0].json.get("species"), "purpleheart")
        self.assertEqual(entities[0].json.get("circumference_cm"), "300")
        self.assertEqual(entities[1].json.get("label"), "200cm mora")
        self.assertEqual(entities[1].json.get("species"), "mora")
        self.assertEqual(entities[1].json.get("circumference_cm"), "200")
        self.assertEqual(EntityHistory.objects.count(), 2)
        self.assertEqual(EntityHistory.objects.first().created_by, self.user)
        self.assertEqual(EntityHistory.objects.last().created_by, self.user)
        self.assertEqual(EntityHistory.objects.first().mutation_type, "create")
        self.assertEqual(EntityHistory.objects.last().mutation_type, "create")

    def test_dry_run(self):
        """Dry-run validates but does not create entities"""
        csv_content = (
            "label,species,circumference_cm\n" "300cm purpleheart,purpleheart,300\n"
        )
        csv_file = self._create_csv_file(csv_content)
        pre_count = Entity.objects.count()

        for row_result in import_entities_from_csv(
            self.entity_list,
            csv_file,
            label_column="label",
            user=self.user,
            dry_run=True,
        ):
            self.assertEqual(row_result.index, 2)
            self.assertEqual(row_result.status, "created")
            self.assertIsNone(row_result.error)

        post_count = Entity.objects.count()

        self.assertEqual(pre_count, post_count)

    def test_default_label_column(self):
        """Default label column is 'label' if not provided"""
        csv_content = (
            "label,species,circumference_cm\n" "300cm purpleheart,purpleheart,300\n"
        )
        csv_file = self._create_csv_file(csv_content)
        # Consume generator by casting into list
        list(
            import_entities_from_csv(
                self.entity_list,
                csv_file,
            )
        )

        self.assertEqual(Entity.objects.count(), 1)
        self.assertEqual(Entity.objects.first().json.get("label"), "300cm purpleheart")

    def test_default_uuid_column(self):
        """Default uuid column is 'uuid' if not provided"""
        csv_content = (
            "label,species,circumference_cm,uuid\n"
            "300cm purpleheart,purpleheart,300,dbee4c32-a922-451c-9df7-42f40bf78f48\n"
        )
        csv_file = self._create_csv_file(csv_content)
        # Consume generator by casting into list
        list(
            import_entities_from_csv(
                self.entity_list,
                csv_file,
            )
        )

        self.assertEqual(Entity.objects.count(), 1)
        self.assertEqual(
            str(Entity.objects.first().uuid), "dbee4c32-a922-451c-9df7-42f40bf78f48"
        )

    def test_default_user(self):
        """Default user is None if not provided"""
        csv_content = (
            "label,species,circumference_cm\n" "300cm purpleheart,purpleheart,300\n"
        )
        csv_file = self._create_csv_file(csv_content)
        # Consume generator by casting into list
        list(
            import_entities_from_csv(
                self.entity_list,
                csv_file,
            )
        )

        self.assertEqual(Entity.objects.count(), 1)
        entity = Entity.objects.first()
        self.assertIsNone(EntityHistory.objects.get(entity=entity).created_by)

    def test_missing_label_column(self):
        """Missing label column raises ValueError"""
        csv_content = "species,circumference_cm\npurpleheart,300\nmora,200\n"
        csv_file = self._create_csv_file(csv_content)

        with self.assertRaises(CSVImportError) as exc_info:
            list(import_entities_from_csv(self.entity_list, csv_file))

        self.assertEqual(str(exc_info.exception), "CSV must include a 'label' column.")

    def test_custom_label_column(self):
        """Custom label column is used if provided"""
        csv_content = (
            "tree_name,species,circumference_cm\n" "300cm purpleheart,purpleheart,300\n"
        )
        csv_file = self._create_csv_file(csv_content)
        # Consume generator by casting into list
        list(
            import_entities_from_csv(
                self.entity_list,
                csv_file,
                label_column="tree_name",
            )
        )

        self.assertEqual(Entity.objects.count(), 1)
        self.assertEqual(Entity.objects.first().json.get("label"), "300cm purpleheart")

    def test_custom_uuid_column(self):
        """Custom uuid column is used if provided"""
        csv_content = (
            "label,species,circumference_cm,entity_id\n"
            "300cm purpleheart,purpleheart,300,dbee4c32-a922-451c-9df7-42f40bf78f48\n"
        )
        csv_file = self._create_csv_file(csv_content)
        # Consume generator by casting into list
        list(
            import_entities_from_csv(
                self.entity_list,
                csv_file,
                uuid_column="entity_id",
            )
        )

        self.assertEqual(Entity.objects.count(), 1)
        self.assertEqual(
            str(Entity.objects.first().uuid), "dbee4c32-a922-451c-9df7-42f40bf78f48"
        )

    def test_unknown_property_column_ignored(self):
        """Unknown property columns are ignored"""
        csv_content = (
            "label,species,circumference_cm,unknown_property\n"
            "300cm purpleheart,purpleheart,300,unknown\n"
        )
        csv_file = self._create_csv_file(csv_content)
        # Consume generator by casting into list
        list(
            import_entities_from_csv(
                self.entity_list,
                csv_file,
            )
        )

        self.assertEqual(Entity.objects.count(), 1)
        entity = Entity.objects.first()
        self.assertEqual(Entity.objects.first().json.get("label"), "300cm purpleheart")
        self.assertEqual(entity.json.get("species"), "purpleheart")
        self.assertEqual(entity.json.get("circumference_cm"), "300")
        self.assertNotIn("unknown_property", entity.json)

    def test_existing_entity_updated(self):
        """Existing entity is updated if uuid is provided"""
        self._simulate_existing_entity()
        csv_content = (
            "label,species,circumference_cm,uuid\n"
            f"450cm purpleheart,purpleheart,450,{self.entity.uuid}\n"
        )
        csv_file = self._create_csv_file(csv_content)

        for row_result in import_entities_from_csv(
            self.entity_list,
            csv_file,
        ):
            self.assertEqual(row_result.index, 2)
            self.assertEqual(row_result.status, "updated")
            self.assertIsNone(row_result.error)

        self.assertEqual(Entity.objects.count(), 1)
        self.entity.refresh_from_db()
        self.assertEqual(self.entity.json.get("label"), "450cm purpleheart")
        self.assertEqual(self.entity.json.get("species"), "purpleheart")
        self.assertEqual(self.entity.json.get("circumference_cm"), "450")

    @patch("onadata.libs.serializers.entity_serializer.EntitySerializer.is_valid")
    def test_errors(self, mock_is_valid):
        """Errors are recorded for invalid rows"""
        mock_is_valid.side_effect = Exception("Invalid data")
        csv_content = (
            "label,species,circumference_cm\n"
            "300cm purpleheart,purpleheart,300\n"
            "200cm mora,mora,200\n"
        )
        csv_file = self._create_csv_file(csv_content)

        for row_result in import_entities_from_csv(
            self.entity_list,
            csv_file,
        ):
            if row_result.index in [2, 3]:
                self.assertEqual(row_result.status, "error")
                self.assertEqual(row_result.error, "Invalid data")

    def test_properties_required_for_create(self):
        """At least one property must be provided for create."""
        csv_content = "label\n" "300cm\n"
        csv_file = self._create_csv_file(csv_content)

        for row_result in import_entities_from_csv(
            self.entity_list,
            csv_file,
        ):
            if row_result.index in [2]:
                self.assertEqual(row_result.status, "error")
                self.assertEqual(
                    row_result.error,
                    "At least 1 property required to create Entity",
                )

    def test_dataset_must_have_properties(self):
        """Entity List must have properties defined prior to import."""
        entity_list = EntityList.objects.create(name="hospitals", project=self.project)
        csv_content = "label,county\n" "Makini,Nairobi\n"
        csv_file = self._create_csv_file(csv_content)

        with self.assertRaises(CSVImportError) as exc_info:
            list(import_entities_from_csv(entity_list, csv_file))

        self.assertEqual(
            str(exc_info.exception), "EntityList has no properties defined."
        )
