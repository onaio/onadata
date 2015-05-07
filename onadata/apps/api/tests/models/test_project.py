from onadata.apps.api import tools
from onadata.apps.logger.models.project import Project
from onadata.apps.api.tests.models.test_abstract_models import\
    TestAbstractModels


class TestProject(TestAbstractModels):

    def test_create_organization_project(self):
        organization = self._create_organization("modilabs", self.user)
        project_name = "demo"
        project = self._create_project(organization, project_name, self.user)
        self.assertIsInstance(project, Project)
        self.assertEqual(project.name, project_name)

        user_deno = self._create_user('deno', 'deno')
        project = tools.create_organization_project(
            organization, project_name, user_deno)
        self.assertIsNone(project)
