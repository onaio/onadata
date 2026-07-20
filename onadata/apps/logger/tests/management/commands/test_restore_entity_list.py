"""Tests for restore_entity_list management command"""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from onadata.apps.logger.models import EntityList
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.user_auth import get_user_default_project


class RestoreEntityListTestCase(TestBase):
    """Tests for restore_entity_list management command"""

    def setUp(self):
        super().setUp()

        self.project = get_user_default_project(self.user)

    def test_restore(self):
        """Soft deleted EntityList is restored"""
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        entity_list.soft_delete(self.user)
        out = StringIO()

        call_command("restore_entity_list", entity_list.pk, stdout=out)

        entity_list.refresh_from_db()
        self.assertIsNone(entity_list.deleted_at)
        self.assertIsNone(entity_list.deleted_by)
        self.assertEqual(entity_list.name, "trees")
        self.assertIn(
            f"Successfully restored EntityList 'trees' with ID {entity_list.pk}",
            out.getvalue(),
        )

    def test_not_soft_deleted(self):
        """Restoring an EntityList that is not soft deleted fails"""
        entity_list = EntityList.objects.create(name="trees", project=self.project)

        with self.assertRaisesRegex(
            CommandError, f"EntityList with ID {entity_list.pk} is not soft-deleted"
        ):
            call_command("restore_entity_list", entity_list.pk)

    def test_does_not_exist(self):
        """Restoring an EntityList that does not exist fails"""
        with self.assertRaisesRegex(
            CommandError, "EntityList with ID 1234 does not exist"
        ):
            call_command("restore_entity_list", 1234)
