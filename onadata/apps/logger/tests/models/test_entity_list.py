"""Tests for module onadata.apps.logger.models.entity_list"""
import pytz
import os
from datetime import datetime
from unittest.mock import patch

from django.core.cache import cache
from django.db.utils import IntegrityError, DataError

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import EntityList, Project
from onadata.libs.utils.user_auth import get_user_default_project


class EntityListTestCase(TestBase):
    """Tests for model EntityList"""

    def setUp(self) -> None:
        super().setUp()

        self.project = get_user_default_project(self.user)
        self.mocked_now = datetime(2023, 11, 8, 13, 17, 0, tzinfo=pytz.utc)
        self.fixture_dir = os.path.join(self.this_directory, "fixtures", "entities")

    @patch("django.utils.timezone.now")
    def test_creation(self, mock_now):
        """We can create an EntityList"""
        mock_now.return_value = self.mocked_now
        entity_list = EntityList.objects.create(
            name="trees", project=self.project, metadata={"foo": "bar"}
        )
        self.assertEqual(EntityList.objects.count(), 1)
        self.assertEqual(f"{entity_list}", f"trees|{self.project}")
        self.assertEqual(entity_list.name, "trees")
        self.assertEqual(entity_list.project, self.project)
        self.assertEqual(entity_list.created_at, self.mocked_now)
        self.assertEqual(entity_list.updated_at, self.mocked_now)
        self.assertEqual(entity_list.metadata, {"foo": "bar"})

    def test_name_project_unique_together(self):
        """No duplicate name and project allowed"""

        EntityList.objects.create(name="trees", project=self.project)

        with self.assertRaises(IntegrityError):
            EntityList.objects.create(name="trees", project=self.project)

        # We can create existing name, new project
        project = Project.objects.create(
            name="Project X",
            organization=self.user,
            created_by=self.user,
        )
        EntityList.objects.create(name="trees", project=project)
        # We can create new name, existing project
        EntityList.objects.create(name="immunization", project=self.project)

    def test_max_name_length(self):
        """Field `name` should not exceed 255 characters"""
        # 256 characters fails
        invalid_name = (
            "yhpcuzuvcjnwiabcvezjyauuqapdfpzxcdhigjagbyvrdmxyvatwdgnq"
            "krbcvgbwidujgnfkvycgwnxmwwtduukxjtndzzehrpddccveevuthhnq"
            "rwiuqvtbfyifxrmwmzewefbyediaahcdetiexpnbfavkfmdebjwweqxp"
            "tjerqhpxwuunkjvikeccwktctibezajwtpzbmpwwnpfinviwgarwhkrt"
            "zueyuxkeecdqecjrzyazfcahbtkrjbbb"
        )
        self.assertEqual(len(invalid_name), 256)

        with self.assertRaises(DataError):
            EntityList.objects.create(name=invalid_name, project=self.project)

        # 255 characters succeeds
        EntityList.objects.create(name=invalid_name[:-1], project=self.project)

    def test_properties(self):
        """Returns the correct dataset properties"""
        # Publish XLSForm and implicity create EntityList
        form_path = os.path.join(self.fixture_dir, "trees_registration.xlsx")
        self._publish_xls_file_and_set_xform(form_path)
        form_path = os.path.join(self.fixture_dir, "trees_registration_height.xlsx")
        self._publish_xls_file_and_set_xform(form_path)
        entity_list = EntityList.objects.first()
        # The properties should be from all forms creating Entities for the dataset
        self.assertCountEqual(
            entity_list.properties,
            ["geometry", "species", "circumference_cm", "height_m"],
        )

    def test_defaults(self):
        """Defaults for optional fields are correct"""
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        self.assertEqual(entity_list.metadata, {})

    def test_current_last_entity_update_time(self):
        """Property `current_last_entity_update_time` works"""
        form_path = os.path.join(self.fixture_dir, "trees_registration.xlsx")
        self._publish_xls_file_and_set_xform(form_path)
        entity_list = EntityList.objects.first()
        # Returns None if no Entities exist
        self.assertIsNone(entity_list.current_last_entity_update_time)
        registration_form = entity_list.registration_forms.first()
        entity_1 = registration_form.entities.create(json={"entity_id": "1"})
        entity_2 = registration_form.entities.create(json={"entity_id": "2"})
        # Returns the datetime of the latest entity created
        entity_list.refresh_from_db()
        self.assertEqual(
            entity_list.current_last_entity_update_time, entity_2.updated_at
        )
        # Returns the datetime of the latest entity updated
        entity_1.save()
        self.assertEqual(
            entity_list.current_last_entity_update_time, entity_1.updated_at
        )

    def test_cached_last_entity_update_time(self):
        """Property `cached_last_entity_update_time` works"""
        form_path = os.path.join(self.fixture_dir, "trees_registration.xlsx")
        self._publish_xls_file_and_set_xform(form_path)
        entity_list = EntityList.objects.first()
        # Returns None if key not available in cache
        self.assertIsNone(entity_list.cached_last_entity_update_time)
        # Returns None if key available but data for entity list not available
        self.assertIsNone(entity_list.cached_last_entity_update_time)
        cache.set("entity_list_updates", {})
        # Returns the datetime if data available cache
        cache.set(
            "entity_list_updates",
            {
                entity_list.pk: {
                    "last_update_time": self.mocked_now.isoformat(),
                }
            },
        )
        self.assertEqual(entity_list.cached_last_entity_update_time, self.mocked_now)

    def test_persisted_last_entity_update_time(self):
        """Property `persisted_last_entity_update_time` works"""
        form_path = os.path.join(self.fixture_dir, "trees_registration.xlsx")
        self._publish_xls_file_and_set_xform(form_path)
        entity_list = EntityList.objects.first()
        # Returns None if data not available in the DB
        self.assertIsNone(entity_list.persisted_last_entity_update_time)
        # Returns datetime  if data persisted in the DB
        entity_list.metadata = {"last_entity_update_time": self.mocked_now.isoformat()}
        entity_list.save()
        self.assertEqual(entity_list.persisted_last_entity_update_time, self.mocked_now)

    def test_last_entity_update_time(self):
        """Property `last_entity_update_time` works"""
        form_path = os.path.join(self.fixture_dir, "trees_registration.xlsx")
        self._publish_xls_file_and_set_xform(form_path)
        entity_list = EntityList.objects.first()
        # Returns None if no cache, persisted or queried datetime exists
        self.assertIsNone(entity_list.last_entity_update_time)
        # Simulate cached last update time
        cached_time = datetime(2024, 1, 24, 11, 31, 0, tzinfo=pytz.utc)
        cache.set(
            "entity_list_updates",
            {
                entity_list.pk: {
                    "last_update_time": cached_time.isoformat(),
                }
            },
        )
        # Simulate persisted last update time
        persisted_time = datetime(2024, 1, 24, 11, 32, 0, tzinfo=pytz.utc)
        entity_list.metadata = {"last_entity_update_time": persisted_time.isoformat()}
        entity_list.save()
        # Simulate existing Entities
        registration_form = entity_list.registration_forms.first()
        registration_form.entities.create(json={"entity_id": "1"})
        entity_2 = registration_form.entities.create(json={"entity_id": "2"})
        # Cached last update time is given priority first
        self.assertEqual(entity_list.last_entity_update_time, cached_time)
        # Persisted last update time is given priority second
        cache.delete("entity_list_updates")
        self.assertEqual(entity_list.last_entity_update_time, persisted_time)
        # Queried last update time is given priority last
        entity_list.metadata = {}
        entity_list.save()
        self.assertEqual(entity_list.last_entity_update_time, entity_2.updated_at)
