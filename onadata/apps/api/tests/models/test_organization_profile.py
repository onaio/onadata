from django.core.cache import cache
from django.db import IntegrityError

from guardian.shortcuts import get_perms

from onadata.apps.api import tools
from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.models.team import Team
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.cache_tools import IS_ORG, safe_delete

from onadata.libs.permissions import OwnerRole


class TestOrganizationProfile(TestBase):

    def test_create_organization_creates_team_and_perms(self):
        # create a user - bob
        profile = tools.create_organization_object("modilabs", self.user)
        profile.save()
        self.assertIsInstance(profile, OrganizationProfile)
        organization_profile = OrganizationProfile.objects.get(
            user__username="modilabs")

        # check organization was created
        self.assertTrue(organization_profile.is_organization)

        self.assertTrue(hasattr(profile, 'metadata'))

        # check that the default team was created
        team_name = "modilabs#%s" % Team.OWNER_TEAM_NAME
        team = Team.objects.get(
            organization=organization_profile.user, name=team_name)
        self.assertIsInstance(team, Team)
        self.assertIn(team.group_ptr, self.user.groups.all())
        self.assertTrue(self.user.has_perm('api.is_org_owner'))

    def test_disallow_same_username_with_different_cases(self):
        tools.create_organization("modilabs", self.user)
        with self.assertRaises(IntegrityError):
            tools.create_organization("ModiLabs", self.user)

    def test_delete_organization(self):
        profile = tools.create_organization_object("modilabs", self.user)
        profile.save()
        profile_id = profile.pk
        count = OrganizationProfile.objects.all().count()
        cache.set('{}{}'.format(IS_ORG, profile_id), True)

        profile.delete()
        safe_delete('{}{}'.format(IS_ORG, profile_id))
        self.assertIsNone(cache.get('{}{}'.format(IS_ORG, profile_id)))
        self.assertEqual(count - 1,
                         OrganizationProfile.objects.all().count())

    def test_org_admin_change_team_role(self):
        """
        Test that a user with org admin role can change members role
        """
        # create an organization
        profile = tools.create_organization_object("onaorg", self.user)
        profile.save()
        self.assertIsInstance(profile, OrganizationProfile)
        ona_org = OrganizationProfile.objects.get(
            user__username="onaorg")
        self.assertTrue(ona_org.is_organization)

        # create a project and team, and add team to project
        ona_project = tools.create_organization_project(
            ona_org.user, 'ona_project', self.user)
        team = tools.get_organization_members_team(ona_org)
        tools.add_team_to_project(team, ona_project)

        # add user to organization
        ivy = self._create_user('ivy', 'ivy')
        tools.add_user_to_organization(ona_org, ivy)

        # assert that user cannot change team role
        permissions = get_perms(ivy, team)
        self.assertEqual(len(permissions), 1)
        self.assertIn('view_team', permissions)

        # make user (ivy) admin of org
        OwnerRole.add(ivy, ona_org)
        self.assertTrue(OwnerRole.user_has_role(ivy, ona_org))

        # assert that user (ivy) can change team role
        permissions = get_perms(ivy, team)
        self.assertIn('change_team', permissions)
        self.assertEqual(len(permissions), 4)
