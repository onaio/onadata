from rest_framework.test import APIRequestFactory

from onadata.apps.logger.models import Project
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.libs.serializers.project_serializer import\
    ProjectSerializer, BaseProjectSerializer
from onadata.libs.permissions import (
    OwnerRole, ReadOnlyRole, ManagerRole, DataEntryRole, EditorMinorRole,
    EditorRole, ReadOnlyRoleNoDownload,  DataEntryMinorRole, DataEntryOnlyRole)
from onadata.libs.models.share_project import ShareProject

class TestBaseProjectSerializer(TestAbstractViewSet):
    def setUp(self):
        self.factory = APIRequestFactory()
        self._login_user_and_profile()
        self.serializer = BaseProjectSerializer()

        self._org_create()
        data = {
                'name': u'demo',
                'owner':
                'http://testserver/api/v1/users/%s' % self.organization.user.username,
                'metadata': {'description': 'Some description',
                             'location': 'Naivasha, Kenya',
                             'category': 'governance'},
                'public': False
            }
        #create the project
        self._project_create(data)

        # create users
        # returns a user profile object
        alice = self._create_user_profile({'username': 'alice'})

        ShareProject(self.project, 'alice', 'readonly').save()

    def test_get_users(self):
        ""
        # Is none when request lacks a project
        users = self.serializer.get_users(None)
        self.assertEqual(users, None)

        # Assert list has members and collaborators when passed 'owner'
        request = self.factory.get('/',
                                   data={'owner': self.organization.user.username},
                                   **self.extra)
        self.serializer.context['request'] = request
        users = self.serializer.get_users(self.project)
        self.assertEqual(users, [{'first_name': u'Bob',
                                  'last_name': u'erama',
                                  'is_org': False,
                                  'role': 'owner',
                                  'user': u'bob'
                                  , 'metadata': {}},
                                 {'first_name': u'Dennis',
                                  'last_name': u'',
                                  'is_org': True,
                                  'role': 'owner',
                                  'user': u'denoinc',
                                  'metadata': {}},
                                 {'first_name': u'',
                                  'last_name': u'',
                                  'is_org': False,
                                  'role': 'readonly',
                                  'user': u'alice',
                                  'metadata': {}}])


        # Assert list has members and NOT collaborators when NOT passed 'owner'
        request = self.factory.get('/', **self.extra)
        request.user = self.user
        self.serializer.context['request'] = request
        users = self.serializer.get_users(self.project)
        self.assertEqual(users, [{'first_name': u'Bob',
                                  'last_name': u'erama',
                                  'is_org': False,
                                  'role': 'owner',
                                  'user': u'bob',
                                  'metadata': {}},
                                 {'first_name': u'Dennis',
                                  'last_name': u'',
                                  'is_org': True,
                                  'role': 'owner',
                                  'user': u'denoinc',
                                  'metadata': {}}])

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
