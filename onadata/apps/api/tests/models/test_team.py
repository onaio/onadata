from django.contrib.auth.models import Permission
from guardian.shortcuts import get_perms

from onadata.apps.api import tools
from onadata.apps.logger.models.project import Project
from onadata.apps.api.models.team import Team
from onadata.apps.api.tests.models.test_abstract_models import (
    TestAbstractModels)
from onadata.libs.permissions import (
    DataEntryRole,
    CAN_VIEW_PROJECT,
    CAN_ADD_XFORM,
    CAN_ADD_SUBMISSIONS_PROJECT,
    CAN_EXPORT_PROJECT,
    CAN_VIEW_PROJECT_DATA,
    CAN_VIEW_PROJECT_ALL,
    get_team_project_default_permissions)


class TestTeam(TestAbstractModels):

    def test_create_organization_team(self):
        profile = tools.create_organization_object("modilabs", self.user)
        profile.save()
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

    def test_add_project_perms_to_team(self):
        # create an org, user, team
        organization = self._create_organization("test org", self.user)
        user_deno = self._create_user('deno', 'deno')

        # add a member to the team
        team = tools.create_organization_team(organization, "test team")
        tools.add_user_to_team(team, user_deno)

        project = Project.objects.create(name="Test Project",
                                         organization=organization,
                                         created_by=user_deno,
                                         metadata='{}')

        # confirm that the team has no permissions on project
        self.assertFalse(get_perms(team, project))
        # set DataEntryRole role of project on team
        DataEntryRole.add(team, project)

        self.assertEqual([CAN_EXPORT_PROJECT, CAN_ADD_SUBMISSIONS_PROJECT,
                          CAN_VIEW_PROJECT, CAN_VIEW_PROJECT_ALL,
                          CAN_VIEW_PROJECT_DATA],
                         sorted(get_perms(team, project)))

        self.assertEqual(get_team_project_default_permissions(team, project),
                         DataEntryRole.name)

        # Add a new user
        user_sam = self._create_user('Sam', 'sammy_')

        self.assertFalse(user_sam.has_perm(CAN_VIEW_PROJECT, project))
        self.assertFalse(user_sam.has_perm(CAN_ADD_XFORM, project))

        # Add the user to the group
        tools.add_user_to_team(team, user_sam)

        # assert that team member has default perm set on team
        self.assertTrue(user_sam.has_perm(CAN_VIEW_PROJECT, project))

        # assert that removing team member revokes perms
        tools.remove_user_from_team(team, user_sam)
        self.assertFalse(user_sam.has_perm(CAN_VIEW_PROJECT, project))
        self.assertFalse(user_sam.has_perm(CAN_ADD_XFORM, project))
