import json
from mock import patch
from operator import itemgetter

from onadata.apps.logger.models import Project
from onadata.apps.logger.models import XForm
from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.libs.permissions import (
    OwnerRole, ReadOnlyRole, ManagerRole, DataEntryRole, EditorRole)
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs import permissions as role


class TestProjectViewSet(TestAbstractViewSet):

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
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.project_data])
        self.assertIn('created_by', response.data[0].keys())

    def test_projects_get(self):
        self._project_create()
        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.project_data)

    def test_projects_tags(self):
        self._project_create()
        view = ProjectViewSet.as_view({
            'get': 'labels',
            'post': 'labels',
            'delete': 'labels'
        })
        list_view = ProjectViewSet.as_view({
            'get': 'list',
        })
        project_id = self.project.pk
        # no tags
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=project_id)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.data, [])
        # add tag "hello"
        request = self.factory.post('/', data={"tags": "hello"}, **self.extra)
        response = view(request, pk=project_id)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'hello'])

        # check filter by tag
        request = self.factory.get('/', data={"tags": "hello"}, **self.extra)

        request.user = self.user
        self.project_data = ProjectSerializer(
            self.project, context={'request': request}).data
        response = list_view(request, pk=project_id)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.project_data])

        request = self.factory.get('/', data={"tags": "goodbye"}, **self.extra)
        response = list_view(request, pk=project_id)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # remove tag "hello"
        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=project_id, label='hello')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.data, [])

    def test_projects_create(self):
        self._project_create()
        self.assertIsNotNone(self.project_data)

        projects = Project.objects.all()
        self.assertEqual(len(projects), 1)

        for project in projects:
            self.assertEqual(self.user, project.created_by)
            self.assertEqual(self.user, project.organization)

    def test_projects_create_no_metadata(self):
        data = {
            'name': u'demo',
            'owner':
            'http://testserver/api/v1/users/%s' % self.user.username,
            'public': False
        }
        self._project_create(project_data=data,
                             merge=False)
        self.assertIsNotNone(self.project)
        self.assertIsNotNone(self.project_data)

        projects = Project.objects.all()
        self.assertEqual(len(projects), 1)

        for project in projects:
            self.assertEqual(self.user, project.created_by)
            self.assertEqual(self.user, project.organization)

    def test_projects_create_many_users(self):
        self._project_create()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)
        self._project_create()
        projects = Project.objects.filter(created_by=self.user)
        self.assertEqual(len(projects), 1)

        for project in projects:
            self.assertEqual(self.user, project.created_by)
            self.assertEqual(self.user, project.organization)

    def test_publish_xls_form_to_project(self):
        self._publish_xls_form_to_project()
        project_name = u'another project'
        self._project_create({'name': project_name})
        self._publish_xls_form_to_project()

    def test_num_datasets(self):
        self._publish_xls_form_to_project()
        request = self.factory.post('/', data={}, **self.extra)
        request.user = self.user
        self.project_data = ProjectSerializer(
            self.project, context={'request': request}).data
        self.assertEqual(self.project_data['num_datasets'], 1)

    def test_last_submission_date(self):
        self._publish_xls_form_to_project()
        self._make_submissions()
        request = self.factory.post('/', data={}, **self.extra)
        request.user = self.user
        self.project_data = ProjectSerializer(
            self.project, context={'request': request}).data
        date_created = self.xform.instances.order_by(
            '-date_created').values_list('date_created', flat=True)[0]
        self.assertEqual(str(self.project_data['last_submission_date']),
                         str(date_created))

    def test_view_xls_form(self):
        self._publish_xls_form_to_project()
        view = ProjectViewSet.as_view({
            'get': 'forms'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.form_data])

    def test_assign_form_to_project(self):
        view = ProjectViewSet.as_view({
            'post': 'forms',
            'get': 'retrieve'
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
        self.assertTrue(self.project.xform_set.filter(pk=self.xform.pk))
        self.assertFalse(old_project.xform_set.filter(pk=self.xform.pk))

        # check if form added appears in the project details
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertIn('forms', response.data.keys())
        self.assertEqual(len(response.data['forms']), 1)

    def test_project_manager_can_assign_form_to_project(self):
        view = ProjectViewSet.as_view({
            'post': 'forms',
            'get': 'retrieve'
        })
        self._publish_xls_form_to_project()
        # alice user as manager to both projects
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        ManagerRole.add(alice_profile.user, self.project)
        self.assertTrue(ManagerRole.user_has_role(alice_profile.user,
                                                  self.project))

        formid = self.xform.pk
        old_project = self.project
        project_name = u'another project'
        self._project_create({'name': project_name})
        self.assertTrue(self.project.name == project_name)
        ManagerRole.add(alice_profile.user, self.project)
        self.assertTrue(ManagerRole.user_has_role(alice_profile.user,
                                                  self.project))
        self._login_user_and_profile(alice_data)

        project_id = self.project.pk
        post_data = {'formid': formid}
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, pk=project_id)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.project.xform_set.filter(pk=self.xform.pk))
        self.assertFalse(old_project.xform_set.filter(pk=self.xform.pk))

        # check if form added appears in the project details
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.assertIn('forms', response.data.keys())
        self.assertEqual(len(response.data['forms']), 1)

    def test_project_users_get_readonly_role_on_add_form(self):
        self._project_create()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        ReadOnlyRole.add(alice_profile.user, self.project)
        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user,
                                                   self.project))
        self._publish_xls_form_to_project()
        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user,
                                                   self.xform))
        self.assertFalse(OwnerRole.user_has_role(alice_profile.user,
                                                 self.xform))

    @patch('onadata.apps.api.viewsets.project_viewset.send_mail')
    def test_project_share_endpoint(self, mock_send_mail):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        projectid = self.project.pk

        ROLES = [ReadOnlyRole,
                 DataEntryRole,
                 EditorRole,
                 ManagerRole,
                 OwnerRole]
        for role_class in ROLES:
            self.assertFalse(role_class.user_has_role(alice_profile.user,
                                                      self.project))

            data = {'username': 'alice', 'role': role_class.name,
                    'email_msg': 'I have shared the project with you'}
            request = self.factory.post('/', data=data, **self.extra)

            view = ProjectViewSet.as_view({
                'post': 'share'
            })
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 204)
            self.assertTrue(mock_send_mail.called)

            self.assertTrue(role_class.user_has_role(alice_profile.user,
                                                     self.project))
            self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user,
                                                       self.xform))
            # Reset the mock called value to False
            mock_send_mail.called = False

            data = {'username': 'alice', 'role': ''}
            request = self.factory.post('/', data=data, **self.extra)
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get('Last-Modified'), None)
            self.assertFalse(mock_send_mail.called)

            role_class._remove_obj_permissions(alice_profile.user,
                                               self.project)

    def test_project_share_remove_user(self):
        self._project_create()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        view = ProjectViewSet.as_view({
            'post': 'share'
        })
        projectid = self.project.pk
        role_class = ReadOnlyRole
        data = {'username': 'alice', 'role': role_class.name}
        request = self.factory.post('/', data=data, **self.extra)
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(role_class.user_has_role(alice_profile.user,
                                                 self.project))

        view = ProjectViewSet.as_view({
            'post': 'share'
        })
        data['remove'] = True
        request = self.factory.post('/', data=data, **self.extra)
        response = view(request, pk=projectid)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(role_class.user_has_role(alice_profile.user,
                                                  self.project))

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

    def test_project_update_shared_cascades_to_xforms(self):
        self._publish_xls_form_to_project()
        view = ProjectViewSet.as_view({
            'patch': 'partial_update'
        })
        projectid = self.project.pk
        data = {'public': 'true'}
        request = self.factory.patch('/', data=data, **self.extra)
        response = view(request, pk=projectid)
        xforms_status = XForm.objects.filter(project__pk=projectid)\
            .values_list('shared', flat=True)
        self.assertTrue(xforms_status[0])
        self.assertEqual(response.status_code, 200)

    def test_project_add_star(self):
        self._project_create()
        self.assertEqual(len(self.project.user_stars.all()), 0)

        view = ProjectViewSet.as_view({
            'post': 'star'
        })
        request = self.factory.post('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.project.reload()

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get('Last-Modified'), None)
        self.assertEqual(len(self.project.user_stars.all()), 1)
        self.assertEqual(self.project.user_stars.all()[0], self.user)

    def test_project_delete_star(self):
        self._project_create()

        view = ProjectViewSet.as_view({
            'delete': 'star',
            'post': 'star'
        })
        request = self.factory.post('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.project.reload()
        self.assertEqual(len(self.project.user_stars.all()), 1)
        self.assertEqual(self.project.user_stars.all()[0], self.user)

        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.project.reload()

        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(self.project.user_stars.all()), 0)

    def test_project_get_starred_by(self):
        self._project_create()

        # add star as bob
        view = ProjectViewSet.as_view({
            'get': 'star',
            'post': 'star'
        })
        request = self.factory.post('/', **self.extra)
        response = view(request, pk=self.project.pk)

        # ensure email not shared
        user_profile_data = self.user_profile_data()
        del user_profile_data['email']

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)

        # add star as alice
        request = self.factory.post('/', **self.extra)
        response = view(request, pk=self.project.pk)

        # get star users as alice
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        alice_profile, bob_profile = sorted(response.data,
                                            key=itemgetter('username'))
        self.assertEquals(sorted(bob_profile.items()),
                          sorted(user_profile_data.items()))
        self.assertEqual(alice_profile['username'], 'alice')

    def test_user_can_view_public_projects(self):
        public_project = Project(name='demo',
                                 shared=True,
                                 metadata=json.dumps({'description': ''}),
                                 created_by=self.user,
                                 organization=self.user)
        public_project.save()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)

        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=public_project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['public'], True)
        self.assertEqual(response.data['projectid'], public_project.pk)
        self.assertEqual(response.data['name'], 'demo')

    def test_projects_same_name_diff_case(self):
        data1 = {
            'name': u'demo',
            'owner':
            'http://testserver/api/v1/users/%s' % self.user.username,
            'metadata': {'description': 'Some description',
                         'location': 'Naivasha, Kenya',
                         'category': 'governance'},
            'public': False
        }
        self._project_create(project_data=data1,
                             merge=False)
        self.assertIsNotNone(self.project)
        self.assertIsNotNone(self.project_data)

        projects = Project.objects.all()
        self.assertEqual(len(projects), 1)

        data2 = {
            'name': u'DEMO',
            'owner':
            'http://testserver/api/v1/users/%s' % self.user.username,
            'metadata': {'description': 'Some description',
                         'location': 'Naivasha, Kenya',
                         'category': 'governance'},
            'public': False
        }
        view = ProjectViewSet.as_view({
            'post': 'create'
        })

        request = self.factory.post(
            '/', data=json.dumps(data2),
            content_type="application/json", **self.extra)

        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get('Last-Modified'), None)
        projects = Project.objects.all()
        self.assertEqual(len(projects), 1)

        for project in projects:
            self.assertEqual(self.user, project.created_by)
            self.assertEqual(self.user, project.organization)

    def test_projects_get_exception(self):
        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)

        # does not exists
        response = view(request, pk=11111)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {u'detail': u'Not found'})

        # invalid id
        response = view(request, pk='1w')
        self.assertEqual(response.status_code, 400)
        error_data = {u'detail': u"Invalid value for project_id '1w' must be a"
                                 " positive integer."}
        self.assertEqual(response.data, error_data)

    def test_publish_to_public_project(self):
        public_project = Project(name='demo',
                                 shared=True,
                                 metadata=json.dumps({'description': ''}),
                                 created_by=self.user,
                                 organization=self.user)
        public_project.save()

        self.project = public_project
        self._publish_xls_form_to_project(public=True)

        self.assertEquals(self.xform.shared, True)
        self.assertEquals(self.xform.shared_data, True)

    def test_publish_to_public_project_public_form(self):
        public_project = Project(name='demo',
                                 shared=True,
                                 metadata=json.dumps({'description': ''}),
                                 created_by=self.user,
                                 organization=self.user)
        public_project.save()

        self.project = public_project

        data = {
            'owner': 'http://testserver/api/v1/users/%s'
            % self.project.organization.username,
            'public': True,
            'public_data': True,
            'description': u'transportation_2011_07_25',
            'downloadable': True,
            'allows_sms': False,
            'encrypted': False,
            'sms_id_string': u'transportation_2011_07_25',
            'id_string': u'transportation_2011_07_25',
            'title': u'transportation_2011_07_25',
            'bamboo_dataset': u''
        }
        self._publish_xls_form_to_project(publish_data=data, merge=False)

        self.assertEquals(self.xform.shared, True)
        self.assertEquals(self.xform.shared_data, True)

    def test_project_all_users_can_share_remove_themselves(self):
        self._project_create()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)

        view = ProjectViewSet.as_view({
            'put': 'share'
        })

        data = {'username': 'alice', 'remove': True}
        for role_name, role_class in role.ROLES.iteritems():

            role_class.add(self.user, self.project)
            data['role'] = role_name

            request = self.factory.put('/', data=data, **self.extra)
            response = view(request, pk=self.project.pk)

            self.assertEqual(response.status_code, 204)

            self.assertFalse(role_class.user_has_role(self.user,
                                                      self.project))

    def test_owner_cannot_remove_self_if_no_other_owner(self):
        self._project_create()

        view = ProjectViewSet.as_view({
            'put': 'share'
        })

        data = {'username': 'bob', 'remove': True, 'role': 'owner'}

        request = self.factory.put('/', data=data, **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 400)
        error = {'remove': [u"Project requires at least one owner"]}
        self.assertEquals(response.data, error)

        self.assertTrue(OwnerRole.user_has_role(self.user,
                                                self.project))

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        profile = self._create_user_profile(alice_data)

        OwnerRole.add(profile.user, self.project)

        view = ProjectViewSet.as_view({
            'put': 'share'
        })

        data = {'username': 'bob', 'remove': True, 'role': 'owner'}

        request = self.factory.put('/', data=data, **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 204)

        self.assertFalse(OwnerRole.user_has_role(self.user,
                                                 self.project))

    def test_last_date_modified_changes_when_adding_new_form(self):
        self._project_create()
        last_date = self.project.date_modified
        self._publish_xls_form_to_project()

        self.project.reload()
        current_last_date = self.project.date_modified

        self.assertNotEquals(last_date, current_last_date)

        self._make_submissions()

        self.project.reload()
        self.assertNotEquals(current_last_date, self.project.date_modified)

    def test_anon_project_form_endpoint(self):
        self._project_create()
        self._publish_xls_form_to_project()

        view = ProjectViewSet.as_view({
            'get': 'forms'
        })

        request = self.factory.get('/')
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 404)

    def test_project_manager_can_delete_xform(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        alice = alice_profile.user
        projectid = self.project.pk

        self.assertFalse(ManagerRole.user_has_role(alice, self.project))

        data = {'username': 'alice', 'role': ManagerRole.name,
                'email_msg': 'I have shared the project with you'}
        request = self.factory.post('/', data=data, **self.extra)

        view = ProjectViewSet.as_view({
            'post': 'share'
        })
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(ManagerRole.user_has_role(alice, self.project))
        self.assertTrue(alice.has_perm('delete_xform', self.xform))
