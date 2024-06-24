"""Tests for module onadata.apps.logger.models.entity_list"""

import pytz
import os
from datetime import datetime
from unittest.mock import patch

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
            name="trees",
            project=self.project,
            num_entities=2,
            last_entity_update_time=self.mocked_now,
        )
        self.assertEqual(EntityList.objects.count(), 1)
        self.assertEqual(f"{entity_list}", f"trees|{self.project}")
        self.assertEqual(entity_list.name, "trees")
        self.assertEqual(entity_list.project, self.project)
        self.assertEqual(entity_list.date_created, self.mocked_now)
        self.assertEqual(entity_list.date_modified, self.mocked_now)
        self.assertEqual(entity_list.num_entities, 2)
        self.assertEqual(entity_list.last_entity_update_time, self.mocked_now)
        self.assertTrue(
            self.user.has_perms(
                [
                    "add_entitylist",
                    "view_entitylist",
                    "change_entitylist",
                    "delete_entitylist",
                ],
                entity_list,
            )
        )

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
        invalid_name = "w" * 256
        self.assertEqual(len(invalid_name), 256)

        with self.assertRaises(DataError):
            EntityList.objects.create(name=invalid_name, project=self.project)

        # 255 characters succeeds
        EntityList.objects.create(name=invalid_name[:-1], project=self.project)

    def test_properties(self):
        """Returns the correct dataset properties"""
        # Publish XLSForm and implicity create EntityList
        self._publish_registration_form(self.user)
        height_md = """
        | survey   |
        |          | type               | name                                       | label                    | save_to                                    |
        |          | geopoint           | location                                   | Tree location            | geometry                                   |
        |          | select_one species | species                                    | Tree species             | species                                    |
        |          | integer            | height                                     | Tree height in m         | height_m                                   |
        |          | text               | intake_notes                               | Intake notes             |                                            |
        | choices  |                    |                                            |                          |                                            |
        |          | list_name          | name                                       | label                    |                                            |
        |          | species            | wallaba                                    | Wallaba                  |                                            |
        |          | species            | mora                                       | Mora                     |                                            |
        |          | species            | purpleheart                                | Purpleheart              |                                            |
        |          | species            | greenheart                                 | Greenheart               |                                            |
        | settings |                    |                                            |                          |                                            |
        |          | form_title         | form_id                                    | version                  | instance_name                              |
        |          | Trees registration | trees_registration_height                  | 2022110901               | concat(${height}, "m ", ${species})|
        | entities |                    |                                            |                          |                                            |
        |          | list_name          | label                                      |                          |                                            |
        |          | trees              | concat(${height}, "m ", ${species}) |                          |                                            |"""
        self._publish_markdown(
            height_md, self.user, self.project, id_string="trees_registration_height"
        )
        entity_list = EntityList.objects.first()
        # The properties should be from all forms creating Entities for the dataset
        self.assertCountEqual(
            entity_list.properties,
            ["geometry", "species", "circumference_cm", "height_m"],
        )

    def test_defaults(self):
        """Defaults for optional fields are correct"""
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        self.assertEqual(entity_list.num_entities, 0)
        self.assertIsNone(entity_list.last_entity_update_time)

    @patch("onadata.apps.logger.signals.set_entity_list_perms_async.delay")
    def test_permissions_applied_async(self, mock_set_perms):
        """Permissions are applied asynchronously"""
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        mock_set_perms.assert_called_once_with(entity_list.pk)
