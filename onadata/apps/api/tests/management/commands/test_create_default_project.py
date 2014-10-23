from django.core.management import call_command

from onadata.apps.api.models.project import Project
from onadata.apps.api.models.project_xform import ProjectXForm
from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.tests.test_base import TestBase


class CommandCreateDefaultProjectTests(TestBase):

    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form_and_submit_instance()

    def test_command(self):
        # Confirm project count is 0
        before_count = Project.objects.all().count()
        self.assertEquals(0, before_count)

        # Call command
        call_command('create_default_project')

        # Confirm project count is 1
        projects = Project.objects.all()
        self.assertEquals(before_count+1, len(projects))

        # Confirm name has username
        project = projects[0]
        self.assertContains(project.name, self.user.username)

        # Confirm projectxform created