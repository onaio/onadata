"""Tests for module onadata.apps.api.tools"""

from django.contrib.auth import get_user_model

from onadata.apps.api.models.organization_profile import (
    OrganizationProfile,
    Team,
    get_organization_members_team,
)
from onadata.apps.api.tools import add_org_user_and_share_projects
from onadata.apps.logger.models.project import Project
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import DataEntryRole, ManagerRole, OwnerRole


User = get_user_model()


class AddOrgUserAndShareProjectsTestCase(TestBase):
    """Tests for method add_org_user_and_share_projects"""

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
        add_org_user_and_share_projects(self.org, self.user, "owner")

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

        add_org_user_and_share_projects(self.org, self.user, "manager")

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

        add_org_user_and_share_projects(self.org, self.user, "manager")

        self.assertTrue(ManagerRole.user_has_role(self.user, self.project))

    def test_role_none(self):
        """role param is None or not provided"""
        # Set default permissions for project
        members_team = get_organization_members_team(self.org)
        DataEntryRole.add(members_team, self.project)

        add_org_user_and_share_projects(self.org, self.user)

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
