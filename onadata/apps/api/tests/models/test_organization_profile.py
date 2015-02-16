from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.api import tools
from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.models.team import Team
from django.db import IntegrityError
from django.core.cache import cache
from onadata.libs.utils.cache_tools import IS_ORG, safe_delete


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
