from main.tests.test_base import MainTestCase
from api import tools


class TestAbstractModels(MainTestCase):

    def _create_organization(self, org_name, user):
        profile = tools.create_organization(org_name, user)
        self.organization = profile.user
        return self.organization

    def _create_project(self, organization, project_name, user):
        project = tools.create_organization_project(
            organization, project_name, user)
        return project
