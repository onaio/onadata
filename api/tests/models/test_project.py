from django.db import IntegrityError

from api import tools
from api.models.project import Project
from api.models.project_xform import ProjectXForm
from api.tests.test_models import TestModels


class TestProject(TestModels):

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
