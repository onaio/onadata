"""Tests for restore_entity_list management command"""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from onadata.apps.logger.models import EntityList, RegistrationForm
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

    def test_restore_by_xform_id(self):
        """Soft deleted EntityList is restored via registration form XForm ID"""
        xform = self._publish_registration_form(self.user)
        entity_list = EntityList.objects.get(name="trees")
        entity_list.soft_delete(self.user)
        out = StringIO()

        call_command("restore_entity_list", xform_id=xform.pk, stdout=out)

        entity_list.refresh_from_db()
        self.assertIsNone(entity_list.deleted_at)
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

    def test_no_entity_list_for_xform(self):
        """No soft-deleted EntityList found for the XForm ID fails"""
        xform = self._publish_registration_form(self.user)

        with self.assertRaisesRegex(
            CommandError,
            f"No soft-deleted EntityList found for XForm with ID {xform.pk}",
        ):
            call_command("restore_entity_list", xform_id=xform.pk)

    def test_multiple_entity_lists_for_xform(self):
        """Multiple soft-deleted EntityLists for the XForm ID fails"""
        xform = self._publish_registration_form(self.user)
        trees = EntityList.objects.get(name="trees")
        shrubs = EntityList.objects.create(name="shrubs", project=self.project)
        RegistrationForm.objects.create(entity_list=shrubs, xform=xform)
        trees.soft_delete(self.user)
        shrubs.soft_delete(self.user)

        with self.assertRaisesRegex(
            CommandError,
            f"Multiple soft-deleted EntityLists found for XForm with ID "
            f"{xform.pk}: {trees.pk}, {shrubs.pk}",
        ):
            call_command("restore_entity_list", xform_id=xform.pk)

    def test_id_or_xform_id_required(self):
        """Exactly one of entity_list_id or --xform-id must be provided"""
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        entity_list.soft_delete(self.user)
        expected_error = "Provide exactly one of entity_list_id or --xform-id"

        with self.assertRaisesRegex(CommandError, expected_error):
            call_command("restore_entity_list")

        with self.assertRaisesRegex(CommandError, expected_error):
            call_command("restore_entity_list", entity_list.pk, xform_id=1)
