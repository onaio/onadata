from rest_framework.test import APIRequestFactory

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
