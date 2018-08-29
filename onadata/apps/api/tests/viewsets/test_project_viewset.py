# -*- coding=utf-8 -*-
"""
Test ProjectViewSet module.
"""
import json
import os
from builtins import str
from future.utils import iteritems
from operator import itemgetter

from django.conf import settings
from django.db.models import Q
from httmock import HTTMock, urlmatch
from mock import MagicMock, patch
import requests

from onadata.apps.api import tools
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.tools import get_organization_owners_team
from onadata.apps.api.viewsets.organization_profile_viewset import \
    OrganizationProfileViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.apps.logger.models import Project, XForm
from onadata.apps.main.models import MetaData
from onadata.libs import permissions as role
from onadata.libs.models.share_project import ShareProject
from onadata.libs.permissions import (ROLES_ORDERED, DataEntryMinorRole,
                                      DataEntryOnlyRole, DataEntryRole,
                                      EditorMinorRole, EditorRole, ManagerRole,
                                      OwnerRole, ReadOnlyRole,
                                      ReadOnlyRoleNoDownload)
from onadata.libs.serializers.project_serializer import (BaseProjectSerializer,
                                                         ProjectSerializer)

ROLES = [ReadOnlyRoleNoDownload,
         ReadOnlyRole,
         DataEntryRole,
         EditorRole,
         ManagerRole,
         OwnerRole]


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$')
def enketo_mock(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = \
        '{\n  "url": "https:\\/\\/dmfrm.enketo.org\\/webform",\n'\
        '  "code": "200"\n}'
    return response


def get_latest_tags(project):
    project.refresh_from_db()
    return [tag.name for tag in project.tags.all()]


class TestProjectViewSet(TestAbstractViewSet):

    def setUp(self):
        super(TestProjectViewSet, self).setUp()
        self.view = ProjectViewSet.as_view({
            'get': 'list',
            'post': 'create'
        })

    @patch('onadata.apps.main.forms.urlopen')
    def test_publish_xlsform_using_url_upload(self, mock_urlopen):
        with HTTMock(enketo_mock):
            self._project_create()
            view = ProjectViewSet.as_view({
                'post': 'forms'
            })

            pre_count = XForm.objects.count()
            project_id = self.project.pk
            xls_url = 'https://ona.io/examples/forms/tutorial/form.xlsx'
            path = os.path.join(
                settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
                "transportation", "transportation_different_id_string.xlsx")

            xls_file = open(path, 'rb')
            mock_urlopen.return_value = xls_file

            post_data = {'xls_url': xls_url}
            request = self.factory.post('/', data=post_data, **self.extra)
            response = view(request, pk=project_id)

            mock_urlopen.assert_called_with(xls_url)
            xls_file.close()
            self.assertEqual(response.status_code, 201)
            self.assertEqual(XForm.objects.count(), pre_count + 1)

    def test_projects_list(self):
        self._project_create()
        request = self.factory.get('/', **self.extra)
        request.user = self.user
        response = self.view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        serializer = BaseProjectSerializer(self.project,
                                           context={'request': request})

        self.assertEqual(response.data, [serializer.data])
        self.assertIn('created_by', list(response.data[0]))

    def test_projects_get(self):
        self._project_create()
        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)
        user_props = ['user', 'first_name', 'last_name', 'role',
                      'is_org', 'metadata']
        user_props.sort()

        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.project_data)
        res_user_props = list(response.data['users'][0])
        res_user_props.sort()
        self.assertEqual(res_user_props, user_props)

    def test_project_get_deleted_form(self):
        self._publish_xls_form_to_project()

        # set the xform in this project to deleted
        self.xform.deleted_at = self.xform.date_created
        self.xform.save()

        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(len(response.data.get('forms')), 0)
        self.assertEqual(response.status_code, 200)

    def test_none_empty_forms_and_dataview_properties_in_returned_json(self):
        self._publish_xls_form_to_project()
        self._create_dataview()

        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertGreater(len(response.data.get('forms')), 0)
        self.assertGreater(
            len(response.data.get('data_views')), 0)

        form_obj_keys = list(response.data.get('forms')[0])
        data_view_obj_keys = list(response.data.get('data_views')[0])
        self.assertEqual(['date_created',
                          'downloadable',
                          'encrypted',
                          'formid',
                          'id_string',
                          'is_merged_dataset',
                          'last_submission_time',
                          'last_updated_at',
                          'name',
                          'num_of_submissions',
                          'published_by_formbuilder',
                          'url'],
                         sorted(form_obj_keys))
        self.assertEqual(['columns',
                          'dataviewid',
                          'date_created',
                          'date_modified',
                          'instances_with_geopoints',
                          'matches_parent',
                          'name',
                          'project',
                          'query',
                          'url',
                          'xform'],
                         sorted(data_view_obj_keys))
        self.assertEqual(response.status_code, 200)

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
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data, [])
        self.assertEqual(get_latest_tags(self.project), [])
        # add tag "hello"
        request = self.factory.post('/', data={"tags": "hello"}, **self.extra)
        response = view(request, pk=project_id)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'hello'])
        self.assertEqual(get_latest_tags(self.project), [u'hello'])

        # check filter by tag
        request = self.factory.get('/', data={"tags": "hello"}, **self.extra)

        self.project.refresh_from_db()
        request.user = self.user
        self.project_data = BaseProjectSerializer(
            self.project, context={'request': request}).data
        response = list_view(request, pk=project_id)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0], self.project_data)

        request = self.factory.get('/', data={"tags": "goodbye"}, **self.extra)
        response = list_view(request, pk=project_id)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # remove tag "hello"
        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=project_id, label='hello')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data, [])
        self.assertEqual(get_latest_tags(self.project), [])

    def test_projects_create(self):
        self._project_create()
        self.assertIsNotNone(self.project_data)

        projects = Project.objects.all()
        self.assertEqual(len(projects), 1)

        for project in projects:
            self.assertEqual(self.user, project.created_by)
            self.assertEqual(self.user, project.organization)

    def test_project_create_other_account(self):  # pylint: disable=C0103
        """
        Test that a user cannot create a project in a different user account
        without the right permission.
        """
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        bob = self.user
        self._login_user_and_profile(alice_data)
        data = {
            "name": "Example Project",
            "owner": "http://testserver/api/v1/users/bob",  # Bob
        }

        # Alice should not be able to create the form in bobs account.
        request = self.factory.post('/projects', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {
            'owner': [u'You do not have permission to create a project in '
                      'the organization {}.'.format(bob)]})
        self.assertEqual(Project.objects.count(), 0)

        # Give Alice the permission to create a project in Bob's account.
        ManagerRole.add(alice_profile.user, bob.profile)
        request = self.factory.post('/projects', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        projects = Project.objects.all()
        self.assertEqual(len(projects), 1)

        for project in projects:
            # Created by Alice
            self.assertEqual(alice_profile.user, project.created_by)
            # But under Bob's account
            self.assertEqual(bob, project.organization)

    def test_create_duplicate_project(self):
        """
        Test creating a project with the same name
        """
        # data to create project
        data = {
            'name': u'demo',
            'owner':
            'http://testserver/api/v1/users/%s' % self.user.username,
            'metadata': {'description': 'Some description',
                         'location': 'Naivasha, Kenya',
                         'category': 'governance'},
            'public': False
        }

        # current number of projects
        count = Project.objects.count()

        # create project using data
        view = ProjectViewSet.as_view({
            'post': 'create'
        })
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 201)
        after_count = Project.objects.count()
        self.assertEqual(after_count, count + 1)

        # create another project using the same data
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {
                u'non_field_errors':
                [u'The fields name, organization must make a unique set.']
            }
        )
        final_count = Project.objects.count()
        self.assertEqual(after_count, final_count)

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
        self.project.refresh_from_db()
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
        self.project.refresh_from_db()
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
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)

        resultset = MetaData.objects.filter(Q(object_id=self.xform.pk), Q(
            data_type='enketo_url') | Q(data_type='enketo_preview_url'))
        url = resultset.get(data_type='enketo_url')
        preview_url = resultset.get(data_type='enketo_preview_url')
        form_metadata = sorted([{
            'id': preview_url.pk,
            'xform': self.xform.pk,
            'data_value': u"https://enketo.ona.io/preview/::YY8M",
            'data_type': u'enketo_preview_url',
            'data_file': None,
            'data_file_type': None,
            'url': 'http://testserver/api/v1/metadata/%s' % preview_url.pk,
            'file_hash': None,
            'media_url': None,
            'date_created': preview_url.date_created
        }, {
            'id': url.pk,
            'data_value': u"https://enketo.ona.io/::YY8M",
            'xform': self.xform.pk,
            'data_file': None,
            'data_type': 'enketo_url',
            'url': 'http://testserver/api/v1/metadata/%s' % url.pk,
            'data_file_type': None,
            'file_hash': None,
            'media_url': None,
            'date_created': url.date_created
        }], key=itemgetter('id'))

        # test metadata content separately
        response_metadata = sorted(
            [dict(item) for item in response.data[0].pop("metadata")],
            key=itemgetter('id'))

        self.assertEqual(response_metadata, form_metadata)

        # remove metadata and date_modified
        self.form_data.pop('metadata')
        self.form_data.pop('date_modified')
        self.form_data.pop('last_updated_at')
        response.data[0].pop('date_modified')
        response.data[0].pop('last_updated_at')
        self.form_data.pop('has_id_string_changed')

        self.assertDictEqual(dict(response.data[0]), dict(self.form_data))

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
        self.assertIn('forms', list(response.data))
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
        ShareProject(self.project, 'alice', 'manager').save()
        self.assertTrue(ManagerRole.user_has_role(alice_profile.user,
                                                  self.project))

        formid = self.xform.pk
        old_project = self.project
        project_name = u'another project'
        self._project_create({'name': project_name})
        self.assertTrue(self.project.name == project_name)
        ShareProject(self.project, 'alice', 'manager').save()
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
        self.assertIn('forms', list(response.data))
        self.assertEqual(len(response.data['forms']), 1)

    def test_project_manager_can_assign_form_to_project_no_perm(self):
        # user must have owner/manager permissions
        view = ProjectViewSet.as_view({
            'post': 'forms',
            'get': 'retrieve'
        })
        self._publish_xls_form_to_project()
        # alice user is not manager to both projects
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        self.assertFalse(ManagerRole.user_has_role(alice_profile.user,
                                                   self.project))

        formid = self.xform.pk
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
        self.assertEqual(response.status_code, 403)

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
    def test_reject_form_transfer_if_target_account_has_id_string_already(
            self, mock_send_mail):
        # create bob's project and publish a form to it
        self._publish_xls_form_to_project()
        projectid = self.project.pk
        bobs_project = self.project

        # create user alice
        alice_data = {
            'username': 'alice',
            'email': 'alice@localhost.com',
            'name': 'alice',
            'first_name': 'alice'
        }
        alice_profile = self._create_user_profile(alice_data)

        # share bob's project with alice
        self.assertFalse(
            ManagerRole.user_has_role(alice_profile.user, bobs_project))

        data = {'username': 'alice', 'role': ManagerRole.name,
                'email_msg': 'I have shared the project with you'}
        request = self.factory.post('/', data=data, **self.extra)
        view = ProjectViewSet.as_view({
            'post': 'share'
        })
        response = view(request, pk=projectid)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(mock_send_mail.called)
        self.assertTrue(
            ManagerRole.user_has_role(alice_profile.user, self.project))
        self.assertTrue(
            ManagerRole.user_has_role(alice_profile.user, self.xform))

        # log in as alice
        self._login_user_and_profile(extra_post_data=alice_data)

        # publish a form to alice's project that shares an id_string with
        # form published by bob
        publish_data = {'owner': 'http://testserver/api/v1/users/alice'}
        self._publish_xls_form_to_project(publish_data=publish_data)

        alices_form = XForm.objects.filter(
            user__username='alice', id_string='transportation_2011_07_25')[0]
        alices_project = alices_form.project
        bobs_form = XForm.objects.filter(
            user__username='bob', id_string='transportation_2011_07_25')[0]
        formid = bobs_form.id

        # try transfering bob's form from bob's project to alice's project
        view = ProjectViewSet.as_view({
            'post': 'forms',
        })
        post_data = {'formid': formid}
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, pk=alices_project.id)
        self.assertEqual(response.status_code, 400)
        self.assertEquals(
            response.data.get('detail'),
            u'Form with the same id_string already exists in this account')

        # try transfering bob's form from to alice's other project with
        # no forms
        self._project_create({'name': 'another project'})
        new_project_id = self.project.id
        view = ProjectViewSet.as_view({
            'post': 'forms',
        })
        post_data = {'formid': formid}
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, pk=new_project_id)
        self.assertEqual(response.status_code, 400)
        self.assertEquals(
            response.data.get('detail'),
            u'Form with the same id_string already exists in this account')

    @patch('onadata.apps.api.viewsets.project_viewset.send_mail')
    def test_allow_form_transfer_if_org_is_owned_by_user(
            self, mock_send_mail):
        # create bob's project and publish a form to it
        self._publish_xls_form_to_project()
        bobs_project = self.project

        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        # access bob's project initially to cache the forms list
        request = self.factory.get('/', **self.extra)
        view(request, pk=bobs_project.pk)

        # create an organization with a project
        self._org_create()
        self._project_create({
            'name': u'organization_project',
            'owner': 'http://testserver/api/v1/users/denoinc',
            'public': False
        })
        org_project = self.project

        self.assertNotEqual(bobs_project.id, org_project.id)

        # try transfering bob's form to an organization project he created
        view = ProjectViewSet.as_view({
            'post': 'forms',
            'get': 'retrieve'
        })
        post_data = {'formid': self.xform.id}
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, pk=self.project.id)

        self.assertEqual(response.status_code, 201)

        # test that cached forms of a source project are cleared. Bob had one
        # forms initially and now it's been moved to the org project.
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=bobs_project.pk)
        bobs_results = response.data
        self.assertListEqual(bobs_results.get('forms'), [])

    @patch('onadata.apps.api.viewsets.project_viewset.send_mail')
    def test_handle_integrity_error_on_form_transfer(self, mock_send_mail):
        # create bob's project and publish a form to it
        self._publish_xls_form_to_project()
        xform = self.xform

        # create an organization with a project
        self._org_create()
        self._project_create({
            'name': u'organization_project',
            'owner': 'http://testserver/api/v1/users/denoinc',
            'public': False
        })

        # publish form to organization project
        self._publish_xls_form_to_project()

        # try transfering bob's form to an organization project he created
        view = ProjectViewSet.as_view({
            'post': 'forms',
        })
        post_data = {'formid': xform.id}
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, pk=self.project.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get('detail'),
            u'Form with the same id_string already exists in this account')

    @patch('onadata.apps.api.viewsets.project_viewset.send_mail')
    def test_form_transfer_when_org_creator_creates_project(
            self, mock_send_mail):
        projects_count = Project.objects.count()
        xform_count = XForm.objects.count()
        user_bob = self.user

        # create user alice with a project
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        self._login_user_and_profile(alice_data)
        self._project_create({
            'name': u'alice\'s project',
            'owner': ('http://testserver/api/v1/users/%s'
                      % alice_profile.user.username),
            'public': False,
        }, merge=False)
        self.assertEqual(self.project.created_by, alice_profile.user)
        alice_project = self.project

        # create org owned by bob then make alice admin
        self._login_user_and_profile(
            {'username': user_bob.username, 'email': user_bob.email})
        self._org_create()
        self.assertEqual(self.organization.created_by, user_bob)
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })
        data = {'username': alice_profile.user.username,
                'role': OwnerRole.name}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, user=self.organization.user.username)
        self.assertEqual(response.status_code, 201)

        owners_team = get_organization_owners_team(self.organization)
        self.assertIn(alice_profile.user, owners_team.user_set.all())

        # let bob create a project in org
        self._project_create({
            'name': u'organization_project',
            'owner': 'http://testserver/api/v1/users/denoinc',
            'public': False,
        })
        self.assertEqual(self.project.created_by, user_bob)
        org_project = self.project
        self.assertEqual(Project.objects.count(), projects_count + 2)

        # let alice create a form in her personal project
        self._login_user_and_profile(alice_data)
        self.project = alice_project
        data = {
            'owner': ('http://testserver/api/v1/users/%s'
                      % alice_profile.user.username),
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
        self.assertEqual(self.xform.created_by, alice_profile.user)
        self.assertEqual(XForm.objects.count(), xform_count + 1)

        # let alice transfer the form to the organization project
        view = ProjectViewSet.as_view({
            'post': 'forms',
        })
        post_data = {'formid': self.xform.id}
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, pk=org_project.id)
        self.assertEqual(response.status_code, 201)

    @patch('onadata.apps.api.viewsets.project_viewset.send_mail')
    def test_form_transfer_when_org_admin_not_creator_creates_project(
            self, mock_send_mail):
        projects_count = Project.objects.count()
        xform_count = XForm.objects.count()
        user_bob = self.user

        # create user alice with a project
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        self._login_user_and_profile(alice_data)
        self._project_create({
            'name': u'alice\'s project',
            'owner': ('http://testserver/api/v1/users/%s'
                      % alice_profile.user.username),
            'public': False,
        }, merge=False)
        self.assertEqual(self.project.created_by, alice_profile.user)
        alice_project = self.project

        # create org owned by bob then make alice admin
        self._login_user_and_profile(
            {'username': user_bob.username, 'email': user_bob.email})
        self._org_create()
        self.assertEqual(self.organization.created_by, user_bob)
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })
        data = {'username': alice_profile.user.username,
                'role': OwnerRole.name}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, user=self.organization.user.username)
        self.assertEqual(response.status_code, 201)

        owners_team = get_organization_owners_team(self.organization)
        self.assertIn(alice_profile.user, owners_team.user_set.all())

        # let alice create a project in org
        self._login_user_and_profile(alice_data)
        self._project_create({
            'name': u'organization_project',
            'owner': 'http://testserver/api/v1/users/denoinc',
            'public': False,
        })
        self.assertEqual(self.project.created_by, alice_profile.user)
        org_project = self.project
        self.assertEqual(Project.objects.count(), projects_count + 2)

        # let alice create a form in her personal project
        self.project = alice_project
        data = {
            'owner': ('http://testserver/api/v1/users/%s'
                      % alice_profile.user.username),
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
        self.assertEqual(self.xform.created_by, alice_profile.user)
        self.assertEqual(XForm.objects.count(), xform_count + 1)

        # let alice transfer the form to the organization project
        view = ProjectViewSet.as_view({
            'post': 'forms',
        })
        post_data = {'formid': self.xform.id}
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, pk=org_project.id)
        self.assertEqual(response.status_code, 201)

    @patch('onadata.apps.api.viewsets.project_viewset.send_mail')
    def test_project_share_endpoint(self, mock_send_mail):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        projectid = self.project.pk

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
            self.assertTrue(role_class.user_has_role(alice_profile.user,
                                                     self.xform))
            # Reset the mock called value to False
            mock_send_mail.called = False

            data = {'username': 'alice', 'role': ''}
            request = self.factory.post('/', data=data, **self.extra)
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get('Cache-Control'), None)
            self.assertFalse(mock_send_mail.called)

            role_class._remove_obj_permissions(alice_profile.user,
                                               self.project)

    @patch('onadata.apps.api.viewsets.project_viewset.send_mail')
    def test_project_share_endpoint_form_published_later(self, mock_send_mail):
        # create project
        self._project_create()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        projectid = self.project.pk

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

            # publish form after project sharing
            self._publish_xls_form_to_project()
            self.assertTrue(role_class.user_has_role(alice_profile.user,
                                                     self.xform))
            # Reset the mock called value to False
            mock_send_mail.called = False

            data = {'username': 'alice', 'role': ''}
            request = self.factory.post('/', data=data, **self.extra)
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get('Cache-Control'), None)
            self.assertFalse(mock_send_mail.called)

            role_class._remove_obj_permissions(alice_profile.user,
                                               self.project)
            self.xform.delete()

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

        data['remove'] = True
        request = self.factory.post('/', data=data, **self.extra)
        response = view(request, pk=projectid)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(role_class.user_has_role(alice_profile.user,
                                                  self.project))

    def test_project_filter_by_owner(self):
        """
        Test projects endpoint filter by owner.
        """
        self._project_create()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com',
                      'first_name': 'Alice', 'last_name': 'Alice'}
        self._login_user_and_profile(alice_data)

        ShareProject(self.project, self.user.username, 'readonly').save()

        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', {'owner': 'bob'}, **self.extra)
        response = view(request, pk=self.project.pk)
        request.user = self.user
        self.project.refresh_from_db()
        bobs_project_data = BaseProjectSerializer(
            self.project, context={'request': request}).data

        self._project_create({'name': 'another project'})

        # both bob's and alice's projects
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        request = self.factory.get('/', {'owner': 'alice'}, **self.extra)
        request.user = self.user
        alice_project_data = BaseProjectSerializer(
            self.project, context={'request': request}).data
        result = [{'owner': p.get('owner'),
                  'projectid': p.get('projectid')} for p in response.data]
        bob_data = {'owner': 'http://testserver/api/v1/users/bob',
                    'projectid': bobs_project_data.get('projectid')}
        alice_data = {'owner': 'http://testserver/api/v1/users/alice',
                      'projectid': alice_project_data.get('projectid')}
        self.assertIn(bob_data, result)
        self.assertIn(alice_data, result)

        # only bob's project
        request = self.factory.get('/', {'owner': 'bob'}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(bobs_project_data, response.data)
        self.assertNotIn(alice_project_data, response.data)

        # only alice's project
        request = self.factory.get('/', {'owner': 'alice'}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(bobs_project_data, response.data)
        self.assertIn(alice_project_data, response.data)

        # none existent user
        request = self.factory.get('/', {'owner': 'noone'}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # authenticated user can view public project
        joe_data = {'username': 'joe', 'email': 'joe@localhost.com'}
        self._login_user_and_profile(joe_data)

        # should not show private projects when filtered by owner
        request = self.factory.get('/', {'owner': 'alice'}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(bobs_project_data, response.data)
        self.assertNotIn(alice_project_data, response.data)

        # should show public project when filtered by owner
        self.project.shared = True
        self.project.save()
        request.user = self.user
        alice_project_data = BaseProjectSerializer(
            self.project, context={'request': request}).data

        request = self.factory.get('/', {'owner': 'alice'}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(alice_project_data, response.data)

        # should show deleted project public project when filtered by owner
        self.project.soft_delete()
        request = self.factory.get('/', {'owner': 'alice'}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([], response.data)

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
        self.project.refresh_from_db()

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get('Cache-Control'), None)
        self.assertEqual(len(self.project.user_stars.all()), 1)
        self.assertEqual(self.project.user_stars.all()[0], self.user)

    def test_create_project_invalid_metadata(self):
        """
        Make sure that invalid metadata values are outright rejected
        Test fix for: https://github.com/onaio/onadata/issues/977
        """
        view = ProjectViewSet.as_view({
            'post': 'create'
        })
        data = {
            'name': u'demo',
            'owner':
            'http://testserver/api/v1/users/%s' % self.user.username,
            'metadata': "null",
            'public': False
        }
        request = self.factory.post(
            '/',
            data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 400)

    def test_project_delete_star(self):
        self._project_create()

        view = ProjectViewSet.as_view({
            'delete': 'star',
            'post': 'star'
        })
        request = self.factory.post('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.project.refresh_from_db()
        self.assertEqual(len(self.project.user_stars.all()), 1)
        self.assertEqual(self.project.user_stars.all()[0], self.user)

        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=self.project.pk)
        self.project.refresh_from_db()

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
        del user_profile_data['metadata']

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
        self.assertEqual(response.get('Cache-Control'), None)
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
        self.assertEqual(response.data, {u'detail': u'Not found.'})

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

    def test_public_form_private_project(self):
        self.project = Project(name='demo', shared=False,
                               metadata=json.dumps({'description': ''}),
                               created_by=self.user, organization=self.user)
        self.project.save()
        self._publish_xls_form_to_project()

        self.assertFalse(self.xform.shared)
        self.assertFalse(self.xform.shared_data)
        self.assertFalse(self.project.shared)

        # when xform.shared is true, project settings does not override
        self.xform.shared = True
        self.xform.save()
        self.project.save()
        self.xform.refresh_from_db()
        self.project.refresh_from_db()
        self.assertTrue(self.xform.shared)
        self.assertFalse(self.xform.shared_data)
        self.assertFalse(self.project.shared)

        # when xform.shared_data is true, project settings does not override
        self.xform.shared = False
        self.xform.shared_data = True
        self.xform.save()
        self.project.save()
        self.xform.refresh_from_db()
        self.project.refresh_from_db()
        self.assertFalse(self.xform.shared)
        self.assertTrue(self.xform.shared_data)
        self.assertFalse(self.project.shared)

        # when xform.shared is true, submissions are made,
        # project settings does not override
        self.xform.shared = True
        self.xform.shared_data = False
        self.xform.save()
        self.project.save()
        self._make_submissions()
        self.xform.refresh_from_db()
        self.project.refresh_from_db()
        self.assertTrue(self.xform.shared)
        self.assertFalse(self.xform.shared_data)
        self.assertFalse(self.project.shared)

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
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)

        view = ProjectViewSet.as_view({
            'put': 'share'
        })

        data = {'username': 'alice', 'remove': True}
        for (role_name, role_class) in iteritems(role.ROLES):

            ShareProject(self.project, 'alice', role_name).save()

            self.assertTrue(role_class.user_has_role(self.user,
                                                     self.project))
            self.assertTrue(role_class.user_has_role(self.user,
                                                     self.xform))
            data['role'] = role_name

            request = self.factory.put('/', data=data, **self.extra)
            response = view(request, pk=self.project.pk)

            self.assertEqual(response.status_code, 204)

            self.assertFalse(role_class.user_has_role(self.user,
                                                      self.project))
            self.assertFalse(role_class.user_has_role(self.user,
                                                      self.xform))

    def test_owner_cannot_remove_self_if_no_other_owner(self):
        self._project_create()

        view = ProjectViewSet.as_view({
            'put': 'share'
        })

        ManagerRole.add(self.user, self.project)

        tom_data = {'username': 'tom', 'email': 'tom@localhost.com'}
        bob_profile = self._create_user_profile(tom_data)

        OwnerRole.add(bob_profile.user, self.project)

        data = {'username': 'tom', 'remove': True, 'role': 'owner'}

        request = self.factory.put('/', data=data, **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 400)
        error = {'remove': [u"Project requires at least one owner"]}
        self.assertEquals(response.data, error)

        self.assertTrue(OwnerRole.user_has_role(bob_profile.user,
                                                self.project))

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        profile = self._create_user_profile(alice_data)

        OwnerRole.add(profile.user, self.project)

        view = ProjectViewSet.as_view({
            'put': 'share'
        })

        data = {'username': 'tom', 'remove': True, 'role': 'owner'}

        request = self.factory.put('/', data=data, **self.extra)
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 204)

        self.assertFalse(OwnerRole.user_has_role(bob_profile.user,
                                                 self.project))

    def test_last_date_modified_changes_when_adding_new_form(self):
        self._project_create()
        last_date = self.project.date_modified
        self._publish_xls_form_to_project()

        self.project.refresh_from_db()
        current_last_date = self.project.date_modified

        self.assertNotEquals(last_date, current_last_date)

        self._make_submissions()

        self.project.refresh_from_db()
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

    def test_move_project_owner(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        alice = alice_profile.user
        projectid = self.project.pk

        self.assertFalse(OwnerRole.user_has_role(alice, self.project))

        view = ProjectViewSet.as_view({
            'patch': 'partial_update'
        })

        data_patch = {
            'owner': 'http://testserver/api/v1/users/%s' % alice.username
        }
        request = self.factory.patch('/', data=data_patch, **self.extra)
        response = view(request, pk=projectid)

        # bob cannot move project if he does not have can_add_project project
        # permission on alice's account.c
        self.assertEqual(response.status_code, 400)

        # Give bob permission.
        ManagerRole.add(self.user, alice_profile)
        request = self.factory.patch('/', data=data_patch, **self.extra)
        response = view(request, pk=projectid)
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEquals(self.project.organization, alice)
        self.assertTrue(OwnerRole.user_has_role(alice, self.project))

    def test_cannot_share_project_to_owner(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()

        data = {'username': self.user.username, 'role': ManagerRole.name,
                'email_msg': 'I have shared the project with you'}
        request = self.factory.post('/', data=data, **self.extra)

        view = ProjectViewSet.as_view({
            'post': 'share'
        })
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['username'], [u"Cannot share project"
                                                     u" with the owner"])
        self.assertTrue(OwnerRole.user_has_role(self.user, self.project))

    def test_project_share_readonly(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        projectid = self.project.pk

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user,
                                                    self.project))

        data = {'username': 'alice', 'role': ReadOnlyRole.name}
        request = self.factory.put('/', data=data, **self.extra)

        view = ProjectViewSet.as_view({
            'put': 'share'
        })
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)

        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user,
                                                   self.project))
        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user,
                                                   self.xform))

        perms = role.get_object_users_with_permissions(self.project)
        for p in perms:
            user = p.get('user')

            if user == alice_profile.user:
                r = p.get('role')
                self.assertEquals(r, ReadOnlyRole.name)

    def test_move_project_owner_org(self):
        # create project and publish form to project
        self._org_create()
        self._publish_xls_form_to_project()

        projectid = self.project.pk

        view = ProjectViewSet.as_view({
            'patch': 'partial_update'
        })
        old_org = self.project.organization

        data_patch = {
            'owner': 'http://testserver/api/v1/users/%s' %
                     self.organization.user.username
        }
        request = self.factory.patch('/', data=data_patch, **self.extra)
        response = view(request, pk=projectid)
        for a in response.data.get('teams'):
            self.assertIsNotNone(a.get('role'))

        self.assertEqual(response.status_code, 200)
        project = Project.objects.get(pk=projectid)

        self.assertNotEqual(old_org, project.organization)

    def test_project_share_inactive_user(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        # set the user inactive
        self.assertTrue(alice_profile.user.is_active)
        alice_profile.user.is_active = False
        alice_profile.user.save()

        projectid = self.project.pk

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user,
                                                    self.project))

        data = {'username': 'alice', 'role': ReadOnlyRole.name}
        request = self.factory.put('/', data=data, **self.extra)

        view = ProjectViewSet.as_view({
            'put': 'share'
        })
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'username': [u'User is not active']})

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user,
                                                    self.project))
        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user,
                                                    self.xform))

    def test_project_share_remove_inactive_user(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        projectid = self.project.pk

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user,
                                                    self.project))

        data = {'username': 'alice', 'role': ReadOnlyRole.name}
        request = self.factory.put('/', data=data, **self.extra)

        view = ProjectViewSet.as_view({
            'put': 'share'
        })
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)

        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user,
                                                   self.project))
        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user,
                                                   self.xform))

        # set the user inactive
        self.assertTrue(alice_profile.user.is_active)
        alice_profile.user.is_active = False
        alice_profile.user.save()

        data = {'username': 'alice', 'role': ReadOnlyRole.name, "remove": True}
        request = self.factory.put('/', data=data, **self.extra)

        self.assertEqual(response.status_code, 204)

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user,
                                                    self.project))
        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user,
                                                    self.xform))

    def test_project_share_readonly_no_downloads(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        tom_data = {'username': 'tom', 'email': 'tom@localhost.com'}
        tom_data = self._create_user_profile(tom_data)
        projectid = self.project.pk

        self.assertFalse(
            ReadOnlyRoleNoDownload.user_has_role(alice_profile.user,
                                                 self.project))

        data = {'username': 'alice', 'role': ReadOnlyRoleNoDownload.name}
        request = self.factory.post('/', data=data, **self.extra)

        view = ProjectViewSet.as_view({
            'post': 'share',
            'get': 'retrieve'
        })
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)

        data = {'username': 'tom', 'role': ReadOnlyRole.name}
        request = self.factory.post('/', data=data, **self.extra)

        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)

        request = self.factory.get('/', **self.extra)

        response = view(request, pk=self.project.pk)

        # get the users
        users = response.data.get('users')

        self.assertEqual(len(users), 3)

        for user in users:
            if user.get('user') == 'bob':
                self.assertEquals(user.get('role'), 'owner')
            elif user.get('user') == 'alice':
                self.assertEquals(user.get('role'), 'readonly-no-download')
            elif user.get('user') == 'tom':
                self.assertEquals(user.get('role'), 'readonly')

    def test_team_users_in_a_project(self):
        self._team_create()
        project = Project.objects.create(name="Test Project",
                                         organization=self.team.organization,
                                         created_by=self.user,
                                         metadata='{}')

        chuck_data = {'username': 'chuck', 'email': 'chuck@localhost.com'}
        chuck_profile = self._create_user_profile(chuck_data)
        user_chuck = chuck_profile.user

        view = TeamViewSet.as_view({
            'post': 'share'})

        self.assertFalse(EditorRole.user_has_role(user_chuck,
                                                  project))
        data = {'role': EditorRole.name,
                'project': project.pk}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 204)
        tools.add_user_to_team(self.team, user_chuck)
        self.assertTrue(EditorRole.user_has_role(user_chuck, project))

        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })

        request = self.factory.get('/', **self.extra)

        response = view(request, pk=project.pk)

        self.assertIsNotNone(response.data['teams'])
        self.assertEquals(3, len(response.data['teams']))
        self.assertEquals(response.data['teams'][2]['role'], 'editor')
        self.assertEquals(response.data['teams'][2]['users'][0],
                          str(chuck_profile.user.username))

    def test_project_accesible_by_admin_created_by_diff_admin(self):
        self._org_create()

        # user 1
        chuck_data = {'username': 'chuck', 'email': 'chuck@localhost.com'}
        chuck_profile = self._create_user_profile(chuck_data)

        # user 2
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        view = OrganizationProfileViewSet.as_view({
            'post': 'members',
        })

        # save the org creator
        bob = self.user

        data = json.dumps(
            {"username": alice_profile.user.username,
             "role": OwnerRole.name})
        # create admin 1
        request = self.factory.post(
            '/', data=data, content_type='application/json', **self.extra)
        response = view(request, user='denoinc')

        self.assertEquals(201, response.status_code)
        data = json.dumps(
            {"username": chuck_profile.user.username,
             "role": OwnerRole.name})
        # create admin 2
        request = self.factory.post(
            '/', data=data, content_type='application/json', **self.extra)
        response = view(request, user='denoinc')

        self.assertEquals(201, response.status_code)

        # admin 2 creates a project
        self.user = chuck_profile.user
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        data = {
            'name': u'demo',
            'owner':
            'http://testserver/api/v1/users/%s' %
            self.organization.user.username,
            'metadata': {'description': 'Some description',
                         'location': 'Naivasha, Kenya',
                         'category': 'governance'},
            'public': False
        }
        self._project_create(project_data=data)

        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })

        # admin 1 tries to access project created by admin 2
        self.user = alice_profile.user
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        request = self.factory.get('/', **self.extra)

        response = view(request, pk=self.project.pk)

        self.assertEquals(200, response.status_code)

        # assert admin can add colaborators
        tompoo_data = {'username': 'tompoo', 'email': 'tompoo@localhost.com'}
        self._create_user_profile(tompoo_data)

        data = {'username': 'tompoo', 'role': ReadOnlyRole.name}
        request = self.factory.put('/', data=data, **self.extra)

        view = ProjectViewSet.as_view({
            'put': 'share'
        })
        response = view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 204)

        self.user = bob
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % bob.auth_token}

        # remove from admin org
        data = json.dumps({"username": alice_profile.user.username})
        view = OrganizationProfileViewSet.as_view({
            'delete': 'members'
        })

        request = self.factory.delete(
            '/', data=data, content_type='application/json', **self.extra)
        response = view(request, user='denoinc')
        self.assertEquals(200, response.status_code)

        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })

        self.user = alice_profile.user
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        request = self.factory.get('/', **self.extra)

        response = view(request, pk=self.project.pk)

        # user cant access the project removed from org
        self.assertEquals(404, response.status_code)

    def test_public_project_on_creation(self):
        view = ProjectViewSet.as_view({
            'post': 'create'
        })

        data = {
            'name': u'demopublic',
            'owner':
            'http://testserver/api/v1/users/%s' % self.user.username,
            'metadata': {'description': 'Some description',
                         'location': 'Naivasha, Kenya',
                         'category': 'governance'},
            'public': True
        }

        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 201)
        project = Project.prefetched.filter(
            name=data['name'], created_by=self.user)[0]

        self.assertTrue(project.shared)

    def test_permission_passed_to_dataview_parent_form(self):

        self._project_create()
        project1 = self.project
        self._publish_xls_form_to_project()
        data = {'name': u'demo2',
                'owner':
                'http://testserver/api/v1/users/%s' % self.user.username,
                'metadata': {'description': 'Some description',
                             'location': 'Naivasha, Kenya',
                             'category': 'governance'},
                'public': False}
        self._project_create(data)
        project2 = self.project

        columns = json.dumps(self.xform.get_field_name_xpaths_only())

        data = {'name': "My DataView",
                'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
                'project': 'http://testserver/api/v1/projects/%s'
                           % project2.pk,
                'columns': columns,
                'query': '[ ]'}
        self._create_dataview(data)

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)

        view = ProjectViewSet.as_view({'put': 'share'})

        data = {'username': 'alice', 'remove': True}
        for (role_name, role_class) in iteritems(role.ROLES):

            ShareProject(self.project, 'alice', role_name).save()

            self.assertFalse(role_class.user_has_role(self.user, project1))
            self.assertTrue(role_class.user_has_role(self.user, project2))
            self.assertTrue(role_class.user_has_role(self.user, self.xform))
            data['role'] = role_name

            request = self.factory.put('/', data=data, **self.extra)
            response = view(request, pk=self.project.pk)

            self.assertEqual(response.status_code, 204)

            self.assertFalse(role_class.user_has_role(self.user,
                                                      project1))
            self.assertFalse(role_class.user_has_role(self.user,
                                                      self.project))
            self.assertFalse(role_class.user_has_role(self.user,
                                                      self.xform))

    def test_permission_not_passed_to_dataview_parent_form(self):

        self._project_create()
        project1 = self.project
        self._publish_xls_form_to_project()
        data = {'name': u'demo2',
                'owner':
                'http://testserver/api/v1/users/%s' % self.user.username,
                'metadata': {'description': 'Some description',
                             'location': 'Naivasha, Kenya',
                             'category': 'governance'},
                'public': False}
        self._project_create(data)
        project2 = self.project

        data = {'name': "My DataView",
                'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
                'project': 'http://testserver/api/v1/projects/%s'
                           % project2.pk,
                'columns': '["name", "age", "gender"]',
                'query': '[{"column":"age","filter":">","value":"20"},'
                         '{"column":"age","filter":"<","value":"50"}]'}

        self._create_dataview(data)

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(alice_data)

        view = ProjectViewSet.as_view({'put': 'share'})

        data = {'username': 'alice', 'remove': True}
        for (role_name, role_class) in iteritems(role.ROLES):

            ShareProject(self.project, 'alice', role_name).save()

            self.assertFalse(role_class.user_has_role(self.user, project1))
            self.assertTrue(role_class.user_has_role(self.user, project2))
            self.assertFalse(role_class.user_has_role(self.user, self.xform))
            data['role'] = role_name

            request = self.factory.put('/', data=data, **self.extra)
            response = view(request, pk=self.project.pk)

            self.assertEqual(response.status_code, 204)

            self.assertFalse(role_class.user_has_role(self.user,
                                                      project1))
            self.assertFalse(role_class.user_has_role(self.user,
                                                      self.project))
            self.assertFalse(role_class.user_has_role(self.user,
                                                      self.xform))

    def test_project_share_xform_meta_perms(self):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        projectid = self.project.pk

        data_value = "editor-minor|dataentry"

        MetaData.xform_meta_permission(self.xform, data_value=data_value)

        for role_class in ROLES_ORDERED:
            self.assertFalse(role_class.user_has_role(alice_profile.user,
                                                      self.project))

            data = {'username': 'alice', 'role': role_class.name}
            request = self.factory.post('/', data=data, **self.extra)

            view = ProjectViewSet.as_view({
                'post': 'share'
            })
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 204)

            self.assertTrue(role_class.user_has_role(alice_profile.user,
                                                     self.project))

            if role_class in [EditorRole, EditorMinorRole]:
                self.assertFalse(
                    EditorRole.user_has_role(alice_profile.user, self.xform))
                self.assertTrue(
                    EditorMinorRole.user_has_role(alice_profile.user,
                                                  self.xform))

            elif role_class in [DataEntryRole, DataEntryMinorRole,
                                DataEntryOnlyRole]:
                self.assertTrue(
                    DataEntryRole.user_has_role(alice_profile.user,
                                                self.xform))

            else:
                self.assertTrue(
                    role_class.user_has_role(alice_profile.user, self.xform))

    @patch('onadata.apps.api.viewsets.project_viewset.send_mail')
    def test_project_share_atomicity(self, mock_send_mail):
        # create project and publish form to project
        self._publish_xls_form_to_project()
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)
        alice = alice_profile.user
        projectid = self.project.pk

        role_class = DataEntryOnlyRole
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

        self.assertTrue(role_class.user_has_role(alice, self.project))
        self.assertTrue(role_class.user_has_role(alice, self.xform))

        data['remove'] = True
        request = self.factory.post('/', data=data, **self.extra)

        mock_rm_xform_perms = MagicMock()
        with patch('onadata.libs.models.share_project.remove_xform_permissions', mock_rm_xform_perms):  # noqa
            mock_rm_xform_perms.side_effect = Exception()
            with self.assertRaises(Exception):
                response = view(request, pk=projectid)
            # permissions have not changed for both xform and project
            self.assertTrue(role_class.user_has_role(alice, self.xform))
            self.assertTrue(role_class.user_has_role(alice, self.project))
            self.assertTrue(mock_rm_xform_perms.called)

        request = self.factory.post('/', data=data, **self.extra)
        response = view(request, pk=projectid)
        self.assertEqual(response.status_code, 204)
        # permissions have changed for both project and xform
        self.assertFalse(role_class.user_has_role(alice, self.project))
        self.assertFalse(role_class.user_has_role(alice, self.xform))

    def test_project_list_by_owner(self):
        # create project and publish form to project
        sluggie_data = {'username': 'sluggie',
                        'email': 'sluggie@localhost.com'}
        self._login_user_and_profile(sluggie_data)
        self._publish_xls_form_to_project()

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        projectid = self.project.pk

        self.assertFalse(ReadOnlyRole.user_has_role(alice_profile.user,
                                                    self.project))

        data = {'username': 'alice', 'role': ReadOnlyRole.name}
        request = self.factory.put('/', data=data, **self.extra)

        view = ProjectViewSet.as_view({
            'put': 'share',
            'get': 'list'
        })
        response = view(request, pk=projectid)

        self.assertEqual(response.status_code, 204)

        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user,
                                                   self.project))
        self.assertTrue(ReadOnlyRole.user_has_role(alice_profile.user,
                                                   self.xform))

        # Should list collaborators
        data = {"owner": "sluggie"}
        request = self.factory.get('/', data=data, **self.extra)
        response = view(request)

        users = response.data[0]['users']
        self.assertEqual(response.status_code, 200)
        self.assertIn({'first_name': u'Bob', 'last_name': u'erama',
                       'is_org': False, 'role': 'readonly', 'user': u'alice',
                       'metadata': {}}, users)

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=projectid)

        # Should not list collaborators
        users = response.data[0]['users']
        self.assertEqual(response.status_code, 200)
        self.assertNotIn({'first_name': u'Bob', 'last_name': u'erama',
                          'is_org': False, 'role': 'readonly',
                          'user': u'alice', 'metadata': {}}, users)

    def test_projects_soft_delete(self):
        self._project_create()

        view = ProjectViewSet.as_view({
            'get': 'list',
            'delete': 'destroy'
        })

        request = self.factory.get('/', **self.extra)
        request.user = self.user
        response = view(request)

        project_id = self.project.pk

        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        serializer = BaseProjectSerializer(self.project,
                                           context={'request': request})

        self.assertEqual(response.data, [serializer.data])
        self.assertIn('created_by', list(response.data[0]))

        request = self.factory.delete('/', **self.extra)
        request.user = self.user
        response = view(request, pk=project_id)
        self.assertEqual(response.status_code, 204)

        self.project = Project.objects.get(pk=project_id)

        self.assertIsNotNone(self.project.deleted_at)
        self.assertTrue('deleted-at' in self.project.name)
        self.assertEqual(self.project.deleted_by, self.user)

        request = self.factory.get('/', **self.extra)
        request.user = self.user
        response = view(request)

        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(serializer.data in response.data)
