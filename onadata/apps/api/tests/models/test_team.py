from django.contrib.auth.models import Permission

from onadata.apps.api import tools
from onadata.apps.api.models.team import Team
from onadata.apps.api.tests.test_abstract_models import TestAbstractModels


class TestTeam(TestAbstractModels):

    def test_create_organization_team(self):
        profile = tools.create_organization("modilabs", self.user)
        organization = profile.user
        team_name = 'dev'
        perms = ['is_org_owner', ]
        tools.create_organization_team(organization, team_name, perms)
        team_name = "modilabs#%s" % team_name
        dev_team = Team.objects.get(organization=organization, name=team_name)

        self.assertIsInstance(dev_team, Team)
        self.assertIsInstance(
            dev_team.permissions.get(codename='is_org_owner'), Permission)

    def test_assign_user_to_team(self):
        # create the organization
        organization = self._create_organization("modilabs", self.user)
        user_deno = self._create_user('deno', 'deno')

        # create another team
        team_name = 'managers'
        team = tools.create_organization_team(organization, team_name)
        tools.add_user_to_team(team, user_deno)

        self.assertIn(team.group_ptr, user_deno.groups.all())

    def test_add_team_to_project(self):
        organization = self._create_organization("modilabs", self.user)
        project_name = "demo"
        team_name = "enumerators"
        project = self._create_project(organization, project_name, self.user)
        team = tools.create_organization_team(organization, team_name)
        result = tools.add_team_to_project(team, project)

        self.assertTrue(result)
        self.assertIn(project, team.projects.all())
