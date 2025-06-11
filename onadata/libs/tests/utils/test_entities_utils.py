# -*- coding: utf-8 -*-
"""
Test entities_utils utility functions.
"""

from datetime import datetime, timedelta
from datetime import timezone as dtz
from unittest.mock import call, patch

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from onadata.apps.logger.models import (
    Entity,
    EntityList,
    Instance,
    RegistrationForm,
    SurveyType,
    XForm,
)
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.entities_utils import (
    commit_cached_elist_num_entities,
    create_entity_from_instance,
    dec_elist_num_entities,
    inc_elist_num_entities,
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
        inc_elist_num_entities(self.entity_list.pk)
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

        inc_elist_num_entities(self.entity_list.pk)

        self.assertEqual(cache.get(self.counter_key), 1)
        self.assertEqual(cache.get(self.ids_key), {self.entity_list.pk})
        self.assertEqual(cache.get(self.created_at_key), mocked_now)
        self.entity_list.refresh_from_db()
        # Database counter should not be updated
        self.assertEqual(self.entity_list.num_entities, 10)
        # New EntityList
        vaccine = EntityList.objects.create(name="vaccine", project=self.project)
        inc_elist_num_entities(vaccine.pk)

        self.assertEqual(cache.get(f"{self.counter_key_prefix}{vaccine.pk}"), 1)
        self.assertEqual(cache.get(self.ids_key), {self.entity_list.pk, vaccine.pk})
        vaccine.refresh_from_db()
        self.assertEqual(vaccine.num_entities, 0)

        # Database counter incremented if cache inacessible
        with patch(
            "onadata.libs.utils.entities_utils._inc_elist_num_entities_cache"
        ) as mock_inc:
            with patch(
                "onadata.libs.utils.entities_utils.logger.exception"
            ) as mock_exc:
                mock_inc.side_effect = ConnectionError
                cache.set(self.counter_key, 3)
                inc_elist_num_entities(self.entity_list.pk)
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
        inc_elist_num_entities(self.entity_list.pk)

        # Timeout should be `None`
        self.assertTrue(
            call(self.counter_key, 1, None) in mock_cache_add.call_args_list
        )
        self.assertTrue(
            call(self.created_at_key, mocked_now, None) in mock_cache_add.call_args_list
        )
        mock_cache_set.assert_called_once_with(
            self.ids_key, {self.entity_list.pk}, None
        )

    def test_time_cache_set_once(self):
        """The cached time of creation is set once"""
        now = timezone.now()
        cache.set(self.created_at_key, now)

        inc_elist_num_entities(self.entity_list.pk)
        # Cache value is not overridden
        self.assertEqual(cache.get(self.created_at_key), now)

    @override_settings(ELIST_COUNTER_COMMIT_FAILOVER_TIMEOUT=3)
    @patch("onadata.libs.utils.entities_utils.report_exception")
    def test_failover(self, mock_report_exc):
        """Failover is executed if commit timeout threshold exceeded"""
        cache_created_at = timezone.now() - timedelta(minutes=10)
        cache.set(self.counter_key, 3)
        cache.set(self.created_at_key, cache_created_at)
        cache.set(self.ids_key, {self.entity_list.pk})

        inc_elist_num_entities(self.entity_list.pk)
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

    @override_settings(ELIST_COUNTER_COMMIT_FAILOVER_TIMEOUT=3)
    @patch("onadata.libs.utils.entities_utils.report_exception")
    def test_failover_report_cache_hit(self, mock_report_exc):
        """Report exception not sent if cache `elist-failover-report-sent` set"""
        cache.set("elist-failover-report-sent", "sent")
        cache_created_at = timezone.now() - timedelta(minutes=10)
        cache.set(self.counter_key, 3)
        cache.set(self.created_at_key, cache_created_at)
        cache.set(self.ids_key, {self.entity_list.pk})

        inc_elist_num_entities(self.entity_list.pk)
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
        dec_elist_num_entities(self.entity_list.pk)
        self.entity_list.refresh_from_db()

        self.assertEqual(self.entity_list.num_entities, 9)
        # Cached counter should not be updated
        self.assertEqual(cache.get(counter_key), 3)

    def test_cache_unlocked(self):
        """Cache counter is decremented if cache is unlocked"""
        counter_key = f"{self.counter_key_prefix}{self.entity_list.pk}"
        cache.set(counter_key, 3)
        dec_elist_num_entities(self.entity_list.pk)

        self.assertEqual(cache.get(counter_key), 2)
        self.entity_list.refresh_from_db()
        # Database counter should not be updated
        self.assertEqual(self.entity_list.num_entities, 10)

        # Database counter is decremented if cache missing
        cache.delete(counter_key)
        dec_elist_num_entities(self.entity_list.pk)
        self.entity_list.refresh_from_db()
        self.assertEqual(self.entity_list.num_entities, 9)

        # Database counter is decremented if cache inaccesible
        with patch(
            "onadata.libs.utils.entities_utils._dec_elist_num_entities_cache"
        ) as mock_dec:
            with patch(
                "onadata.libs.utils.entities_utils.logger.exception"
            ) as mock_exc:
                mock_dec.side_effect = ConnectionError
                cache.set(counter_key, 3)
                dec_elist_num_entities(self.entity_list.pk)
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
