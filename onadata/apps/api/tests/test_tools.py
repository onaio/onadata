"""Tests for module onadata.apps.api.tools"""

from django.contrib.auth import get_user_model
from django.core.cache import cache

from onadata.apps.api.models.organization_profile import (
    OrganizationProfile,
    Team,
    get_organization_members_team,
)
from onadata.apps.api.tools import add_user_to_organization, invalidate_xform_list_cache
from onadata.apps.logger.models.project import Project
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import ROLES, DataEntryRole, ManagerRole, OwnerRole

User = get_user_model()


class AddUserToOrganizationTestCase(TestBase):
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
