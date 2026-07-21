"""Tests for module onadata.apps.api.tools"""

from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from openpyxl import Workbook

from onadata.apps.api.models.organization_profile import (
    OrganizationProfile,
    Team,
    get_organization_members_team,
)
from onadata.apps.api.tools import (
    add_user_to_organization,
    do_publish_xlsform,
    invalidate_xform_list_cache,
    remove_user_from_organization,
)
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import ROLES, DataEntryRole, ManagerRole, OwnerRole

User = get_user_model()


class DoPublishXLSFormTestCase(TestBase):
    """Tests for do_publish_xlsform"""

    def test_update_with_deleted_twin(self):
        """Update is applied to the active form when a deleted twin exists"""
        id_string = "x" * 95
        md = """
        | survey |
        |        | type              | name   | label   |
        |        | select one fruits | fruit  | Fruit   |
        | choices |
        |         | list name         | name   | label  |
        |         | fruits            | orange | Orange |
        """
        dd = self._publish_markdown(md, self.user, id_string=id_string)
        deleted_xform = XForm.objects.get(pk=dd.pk)
        deleted_xform.soft_delete(self.user)
        new_dd = self._publish_markdown(md, self.user, id_string=id_string)
        active_xform = XForm.objects.get(pk=new_dd.pk)
        xls_file = self._create_xls_form(id_string, title="Fruits updated")

        survey = do_publish_xlsform(
            self.user,
            None,
            {"xls_file": xls_file},
            self.user,
            id_string=id_string,
            project=self.project,
        )

        self.assertEqual(survey.pk, active_xform.pk)
        active_xform.refresh_from_db()
        self.assertEqual(active_xform.title, "Fruits updated")

    def _create_xls_form(self, id_string, title):
        """Returns an XLSForm file with the given id_string and title"""
        workbook = Workbook()
        survey_sheet = workbook.active
        survey_sheet.title = "survey"
        survey_sheet.append(["type", "name", "label"])
        survey_sheet.append(["text", "fruit", "Fruit"])
        settings_sheet = workbook.create_sheet("settings")
        settings_sheet.append(["form_title", "form_id"])
        settings_sheet.append([title, id_string])
        file = BytesIO()
        workbook.save(file)
        return SimpleUploadedFile(
            "fruits.xlsx",
            file.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )


class AddUserToOrgTestCase(TestBase):
    """Tests for add_user_to_organization"""

    def setUp(self) -> None:
        super().setUp()

        self.org_user = User.objects.create(username="onaorg")
        alice = self._create_user("alice", "1234&&")
        self.org = OrganizationProfile.objects.create(
            user=self.org_user, name="Ona Org", creator=alice
        )
        self.project = Project.objects.create(
            name="Demo", organization=self.org_user, created_by=alice
        )

    def test_add_owner(self):
        """Owner added to org and projects shared"""
        add_user_to_organization(self.org, self.user, "owner")

        self.user.refresh_from_db()
        owner_team = Team.objects.get(name=f"{self.org_user.username}#Owners")
        members_team = Team.objects.get(name=f"{self.org_user.username}#members")
        self.assertTrue(
            owner_team.user_set.filter(username=self.user.username).exists()
        )
        self.assertTrue(
            members_team.user_set.filter(username=self.user.username).exists()
        )
        self.assertTrue(OwnerRole.user_has_role(self.user, self.project))
        self.assertTrue(OwnerRole.user_has_role(self.user, self.org))

    def test_non_owner(self):
        """Non-owners add to org and projects shared

        Non-owners should be assigned default project permissions
        """
        # Set default permissions for project
        members_team = get_organization_members_team(self.org)
        DataEntryRole.add(members_team, self.project)

        add_user_to_organization(self.org, self.user, "manager")

        self.user.refresh_from_db()
        owner_team = Team.objects.get(name=f"{self.org_user.username}#Owners")
        members_team = Team.objects.get(name=f"{self.org_user.username}#members")
        self.assertFalse(
            owner_team.user_set.filter(username=self.user.username).exists()
        )
        self.assertTrue(
            members_team.user_set.filter(username=self.user.username).exists()
        )
        self.assertTrue(DataEntryRole.user_has_role(self.user, self.project))
        self.assertTrue(ManagerRole.user_has_role(self.user, self.org))

    def test_project_created_by_manager(self):
        """A manager is assigned manager role on projects they created"""
        self.project.created_by = self.user
        self.project.save()

        add_user_to_organization(self.org, self.user, "manager")

        self.assertTrue(ManagerRole.user_has_role(self.user, self.project))

    def test_role_none(self):
        """role param is None or not provided"""
        # Set default permissions for project
        members_team = get_organization_members_team(self.org)
        DataEntryRole.add(members_team, self.project)

        add_user_to_organization(self.org, self.user)

        self.user.refresh_from_db()
        owner_team = Team.objects.get(name=f"{self.org_user.username}#Owners")
        members_team = Team.objects.get(name=f"{self.org_user.username}#members")
        self.assertFalse(
            owner_team.user_set.filter(username=self.user.username).exists()
        )
        self.assertTrue(
            members_team.user_set.filter(username=self.user.username).exists()
        )
        self.assertTrue(DataEntryRole.user_has_role(self.user, self.project))


class RemoveUserFromOrgTestCase(TestBase):
    """Tests for remove_user_from_organization"""

    def setUp(self) -> None:
        super().setUp()

        self.org_user = User.objects.create(username="onaorg")
        self.user = self._create_user("alice", "1234&&")
        self.org = OrganizationProfile.objects.create(
            user=self.org_user, name="Ona Org", creator=self.user
        )
        self.project = Project.objects.create(
            name="Demo", organization=self.org_user, created_by=self.user
        )
        self.owner_team, _ = Team.objects.get_or_create(
            name=f"{self.org_user.username}#Owners", organization=self.org_user
        )
        self.members_team, _ = Team.objects.get_or_create(
            name=f"{self.org_user.username}#members", organization=self.org_user
        )

    def _add_user_to_org(self, is_owner=True):
        self.user.groups.add(self.members_team)

        if is_owner:
            self.user.groups.add(self.owner_team)

            OwnerRole.add(self.user, self.org)
            OwnerRole.add(self.user, self.org.userprofile_ptr)
            OwnerRole.add(self.user, self.project)

        else:
            DataEntryRole.add(self.user, self.project)

    def test_owner_removed(self):
        """Owner is removed from org and all projects"""
        self._add_user_to_org()

        # Confirm user belongs to the org and projects shared with them
        self.assertTrue(
            self.owner_team.user_set.filter(username=self.user.username).exists()
        )
        self.assertTrue(
            self.members_team.user_set.filter(username=self.user.username).exists()
        )
        self.assertTrue(OwnerRole.user_has_role(self.user, self.project))
        self.assertTrue(OwnerRole.user_has_role(self.user, self.org))
        self.assertTrue(OwnerRole.user_has_role(self.user, self.org.userprofile_ptr))

        remove_user_from_organization(self.org, self.user)

        self.assertFalse(
            self.owner_team.user_set.filter(username=self.user.username).exists()
        )
        self.assertFalse(
            self.members_team.user_set.filter(username=self.user.username).exists()
        )
        self.assertFalse(OwnerRole.user_has_role(self.user, self.project))
        self.assertFalse(OwnerRole.user_has_role(self.user, self.org))
        self.assertFalse(OwnerRole.user_has_role(self.user, self.org.userprofile_ptr))

    def test_non_owner(self):
        """Non-owner is removed from org and all projects"""
        self._add_user_to_org(False)

        # Confirm user belongs to the org and projects shared with them
        self.assertTrue(
            self.members_team.user_set.filter(username=self.user.username).exists()
        )
        self.assertTrue(DataEntryRole.user_has_role(self.user, self.project))

        remove_user_from_organization(self.org, self.user)

        self.assertFalse(
            self.members_team.user_set.filter(username=self.user.username).exists()
        )
        self.assertFalse(DataEntryRole.user_has_role(self.user, self.project))

    @patch("onadata.apps.api.tools.invalidate_organization_cache")
    def test_cache_invalidated(self, mock_invalidate_cache):
        """Cache is invalidated on removing user from org"""
        remove_user_from_organization(self.org, self.user)

        mock_invalidate_cache.assert_called_once_with(self.org_user.username)

    @patch("onadata.apps.api.tasks.share_project_async.delay")
    def test_projects_unassigned_async(self, mock_remove_project):
        """Projects are unassigned asynchronously after removing user from org"""
        self._add_user_to_org(False)

        remove_user_from_organization(self.org, self.user)

        mock_remove_project.assert_called_once_with(
            self.project.pk, self.user.username, "dataentry", remove=True
        )


class InvalidateXFormListCacheTestCase(TestBase):
    """Tests for invalidate_xform_list_cache"""

    def setUp(self):
        super().setUp()

        self._publish_transportation_form()
        self.cache_keys = [
            f"xfm-list-{self.xform.pk}-XForm-anon",
            f"xfm-list-{self.xform.project.pk}-Project-anon",
        ]

        # Simulate cached data
        for role in ROLES:
            self.cache_keys.extend(
                [
                    f"xfm-list-{self.xform.pk}-XForm-{role}",
                    f"xfm-list-{self.xform.project.pk}-Project-{role}",
                ]
            )

        for key in self.cache_keys:
            cache.set(key, "data")

    def test_cache_invalidated(self):
        """Cache invalidated for xform and project"""
        self.assertIsNotNone(cache.get(f"xfm-list-{self.xform.pk}-XForm-anon"))
        self.assertIsNotNone(
            cache.get(f"xfm-list-{self.xform.project.pk}-Project-anon")
        )

        for role in ROLES:
            self.assertIsNotNone(cache.get(f"xfm-list-{self.xform.pk}-XForm-{role}"))
            self.assertIsNotNone(
                cache.get(f"xfm-list-{self.xform.project.pk}-Project-{role}")
            )

        invalidate_xform_list_cache(self.xform)

        self.assertIsNone(cache.get(f"xfm-list-{self.xform.pk}-XForm-anon"))
        self.assertIsNone(cache.get(f"xfm-list-{self.xform.project.pk}-Project-anon"))

        for role in ROLES:
            self.assertIsNone(cache.get(f"xfm-list-{self.xform.pk}-XForm-{role}"))
            self.assertIsNone(
                cache.get(f"xfm-list-{self.xform.project.pk}-Project-{role}")
            )
