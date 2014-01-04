from main.tests.test_base import TestBase
from api import tools
from api.models.organization_profile import OrganizationProfile
from api.models.team import Team


class TestOrganizationProfile(TestBase):
    def test_create_organization_creates_team_and_perms(self):
        # create a user - bob
        profile = tools.create_organization("modilabs", self.user)
        self.assertIsInstance(profile, OrganizationProfile)
        organization_profile = OrganizationProfile.objects.get(
            user__username="modilabs")

        # check organization was created
        self.assertTrue(organization_profile.is_organization)

        # check that the default team was created
        team_name = "modilabs#%s" % Team.OWNER_TEAM_NAME
        team = Team.objects.get(
            organization=organization_profile.user, name=team_name)
        self.assertIsInstance(team, Team)
        self.assertIn(team.group_ptr, self.user.groups.all())
        self.assertTrue(self.user.has_perm('api.is_org_owner'))
