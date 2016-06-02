from rest_framework.test import APIRequestFactory

from onadata.apps.logger.models import Project
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.libs.serializers.project_serializer import\
    ProjectSerializer


class TestProjectSerializer(TestAbstractViewSet):

    def setUp(self):
        self.serializer = ProjectSerializer()
        self.factory = APIRequestFactory()
        self._login_user_and_profile()

    def test_get_users_none(self):
        perms = self.serializer.get_users(None)
        self.assertEqual(perms, None)

    def test_get_project_forms(self):
        # create a project with a form
        self._publish_xls_form_to_project()

        project = Project.objects.last()
        form = project.xform_set.last()

        request = self.factory.get('/', **self.extra)
        request.user = self.user

        serializer = ProjectSerializer(project)
        serializer.context['request'] = request

        self.assertEqual(len(serializer.data['forms']), 1)
        self.assertEqual(serializer.data['forms'][0]['encrypted'], False)
        self.assertEqual(serializer.data['num_datasets'], 1)

        # delete form in project
        form.delete()

        # Check that project has no forms
        self.assertIsNone(project.xform_set.last())
        serializer = ProjectSerializer(project, context={'request': request})
        self.assertEqual(len(serializer.data['forms']), 0)
        self.assertEqual(serializer.data['num_datasets'], 0)
