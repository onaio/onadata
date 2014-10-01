from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from onadata.apps.api import tools
from onadata.apps.api.models.project import Project
from onadata.apps.api.models.team import Team
from onadata.apps.api.tests.models.test_abstract_models import (
    TestAbstractModels)
from onadata.libs.permissions import (
    DataEntryRole,
    CAN_VIEW_PROJECT,
    CAN_ADD_XFORM)


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

        # confirm that the team has no permissions
        self.assertFalse(team.groupobjectpermission_set.all())
        # set DataEntryRole role of project on team
        DataEntryRole.add(team, project)

        content_type = ContentType.objects.get(
            model=project.__class__.__name__.lower(),
            app_label=project.__class__._meta.app_label)

        object_permissions = team.groupobjectpermission_set.filter(
            object_pk=project.pk, content_type=content_type)

        permission_names = sorted(
            [p.permission.codename for p in object_permissions])
        self.assertEqual([CAN_ADD_XFORM, CAN_VIEW_PROJECT], permission_names)

        # Add a new user
        user_sam = self._create_user('Sam', 'sammy_')

        self.assertFalse(user_sam.has_perm(CAN_VIEW_PROJECT, project))
        self.assertFalse(user_sam.has_perm(CAN_ADD_XFORM, project))

        # Add the user to the group
        tools.add_user_to_team(team, user_sam)

        # assert that team member has default perm set on team
        self.assertTrue(user_sam.has_perm(CAN_VIEW_PROJECT, project))
        self.assertTrue(user_sam.has_perm(CAN_ADD_XFORM, project))
