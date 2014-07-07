import json
from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.libs.permissions import (
    OwnerRole, ReadOnlyRole, ManagerRole, DataEntryRole, EditorRole)
from onadata.apps.api.models import Project


class TestProjectViewset(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = ProjectViewSet.as_view({
            'get': 'list',
            'post': 'create'
        })

    def test_projects_list(self):
        self._project_create()
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.project_data])

    def test_projects_get(self):
        self._project_create()
        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.project_data)

    def test_projects_create(self):
        self._project_create()

    def test_publish_xls_form_to_project(self):
        self._publish_xls_form_to_project()

    def test_view_xls_form(self):
        self._publish_xls_form_to_project()
        view = ProjectViewSet.as_view({
            'get': 'forms'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.form_data])
        response = view(request, pk=self.project.pk, formid=self.xform.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.form_data)

    def test_assign_form_to_project(self):
        view = ProjectViewSet.as_view({
            'post': 'forms'
        })
        self._publish_xls_form_to_project()
        formid = self.xform.pk
        old_project = self.project
        project_name = u'another project'
        self._project_create({'name': project_name})
        self.assertTrue(self.project.name == project_name)

        project_id = self.project.pk
        post_data = {'formid': formid}
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, pk=project_id)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.project.projectxform_set.filter(xform=self.xform))
        self.assertFalse(old_project.projectxform_set.filter(xform=self.xform))

    def test_project_share_endpoint(self):
        self._project_create()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        view = ProjectViewSet.as_view({
            'post': 'share'
        })
        projectid = self.project.pk

        ROLES = [ReadOnlyRole,
                 DataEntryRole,
                 EditorRole,
                 ManagerRole,
                 OwnerRole]
        for role_class in ROLES:
            self.assertFalse(role_class.has_role(alice_profile.user,
                                                 self.project))

            data = {'username': 'alice', 'role': role_class.name}
            request = self.factory.post('/', data=data, **self.extra)
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 204)
            self.assertTrue(role_class.has_role(alice_profile.user,
                                                self.project))

            data = {'username': 'alice', 'role': ''}
            request = self.factory.post('/', data=data, **self.extra)
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 400)

    def test_project_filter_by_owner(self):
        self._project_create()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)

        ReadOnlyRole.add(self.user, self.project)

        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)
        updated_project_data = response.data

        self._project_create({'name': 'another project'})

        # both bob's and alice's projects
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(updated_project_data, response.data)
        self.assertIn(self.project_data, response.data)

        # only bob's project
        request = self.factory.get('/', {'owner': 'bob'}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(updated_project_data, response.data)
        self.assertNotIn(self.project_data, response.data)

        # only alice's project
        request = self.factory.get('/', {'owner': 'alice'}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(updated_project_data, response.data)
        self.assertIn(self.project_data, response.data)

        # none existent user
        request = self.factory.get('/', {'owner': 'noone'}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_project_partial_updates(self):
        self._project_create()
        view = ProjectViewSet.as_view({
            'patch': 'partial_update'
        })
        projectid = self.project.pk
        metadata = '{"description": "Lorem ipsum",' \
                   '"location": "Nakuru, Kenya",' \
                   '"category": "water"' \
                   '}'
        json_metadata = json.loads(metadata)
        data = {'metadata': metadata}
        request = self.factory.patch('/', data=data, **self.extra)
        response = view(request, pk=projectid)
        project = Project.objects.get(pk=projectid)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(project.metadata, json_metadata)

    def test_project_put_updates(self):
        self._project_create()
        view = ProjectViewSet.as_view({
            'put': 'update'
        })
        projectid = self.project.pk
        data = {
            'name': u'updated name',
            'owner': 'http://testserver/api/v1/users/%s' % self.user.username,
            'metadata': {'description': 'description',
                         'location': 'Nairobi, Kenya',
                         'category': 'health'}
        }
        data.update({'metadata': json.dumps(data.get('metadata'))})
        request = self.factory.put('/', data=data, **self.extra)
        response = view(request, pk=projectid)
        data.update({'metadata': json.loads(data.get('metadata'))})
        self.assertDictContainsSubset(data, response.data)

    def test_project_partial_updates_to_existing_metadata(self):
        self._project_create()
        view = ProjectViewSet.as_view({
            'patch': 'partial_update'
        })
        projectid = self.project.pk
        metadata = '{"description": "Changed description"}'
        json_metadata = json.loads(metadata)
        data = {'metadata': metadata}
        request = self.factory.patch('/', data=data, **self.extra)
        response = view(request, pk=projectid)
        project = Project.objects.get(pk=projectid)
        json_metadata.update(project.metadata)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(project.metadata, json_metadata)
