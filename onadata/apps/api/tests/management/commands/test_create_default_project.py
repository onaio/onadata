from django.core.management import call_command

from onadata.apps.api.models.project import Project
from onadata.apps.api.models.project_xform import ProjectXForm
from onadata.apps.main.tests.test_base import TestBase


class CommandCreateDefaultProjectTests(TestBase):

    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self._publish_transportation_form()

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
        name = self.user.username + '\'s Project'
        self.assertEquals(project.name, name)
        self.assertEquals(project.metadata['description'], 'Default Project')

        # Confirm projectxform created
        proj_xform = ProjectXForm.objects.get(xform=self.xform)

        self.assertEquals(project, proj_xform.project)

        # Test it does not affect the forms already in a project
        self._create_user_and_login("alice", "alice")
        self._publish_transportation_form()
        project = Project.objects.create(name=name,
                                         organization=self.user,
                                         created_by=self.user,
                                         metadata=None)
        ProjectXForm.objects.create(xform=self.xform,
                                    project=project,
                                    created_by=self.user)

        projects = Project.objects.all()
        self.assertEquals(len(projects), 2)

        # Call command
        call_command('create_default_project')

        projects = Project.objects.all()
        self.assertEquals(len(projects), 2)
