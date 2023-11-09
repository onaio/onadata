"""Tests for module onadata.apps.logger.models.entity_list"""
import pytz
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

    @patch("django.utils.timezone.now")
    def test_creation(self, mock_now):
        """We can create an EntityList"""
        mock_now.return_value = self.mocked_now
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        self.assertEqual(EntityList.objects.count(), 1)
        self.assertEqual(f"{entity_list}", f"trees|{self.project}")
        self.assertEqual(entity_list.name, "trees")
        self.assertEqual(entity_list.project, self.project)
        self.assertEqual(entity_list.created_at, self.mocked_now)
        self.assertEqual(entity_list.updated_at, self.mocked_now)

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
