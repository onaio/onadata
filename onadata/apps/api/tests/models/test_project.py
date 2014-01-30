from django.db import IntegrityError

from onadata.apps.api import tools
from onadata.apps.api.models.project import Project
from onadata.apps.api.models.project_xform import ProjectXForm
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

    def test_add_form_to_project(self):
        organization = self._create_organization("modilabs", self.user)
        project_name = "demo"
        project = self._create_project(organization, project_name, self.user)
        self._publish_transportation_form()
        count = ProjectXForm.objects.count()
        project_xform = tools.add_xform_to_project(
            self.xform, project, self.user)
        self.assertEqual(ProjectXForm.objects.count(), count + 1)
        self.assertIsInstance(project_xform, ProjectXForm)
        with self.assertRaises(IntegrityError):
            tools.add_xform_to_project(
                self.xform, project, self.user)
