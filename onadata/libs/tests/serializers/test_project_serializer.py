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

    def test_get_project_permissions_none(self):
        perms = self.serializer.get_project_permissions(None)
        self.assertEqual(perms, [])

    def test_project_serializer_restore_object(self):
        attrs = {'shared': True,
                 'organization': self.user,
                 'name': 'some bla',
                 'metadata': {'category': 'general'}}

        request = self.factory.get('/', **self.extra)
        request.user = self.user
        self.serializer.context['request'] = request
        project = self.serializer.restore_object(attrs)
        self.assertTrue(project.shared)

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
        self.assertEqual(serializer.data['num_datasets'], 1)

        # delete form in project
        form.delete()

        # Check that project has no forms
        self.assertIsNone(project.xform_set.last())
        serializer = ProjectSerializer(project, context={'request': request})
        self.assertEqual(len(serializer.data['forms']), 0)
        self.assertEqual(serializer.data['num_datasets'], 0)
