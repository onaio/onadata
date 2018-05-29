import json
from mock import patch
from builtins import str as text

from django.contrib.auth.models import User

from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.organization_profile_viewset import\
    OrganizationProfileViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.libs.permissions import OwnerRole
from onadata.apps.api.tools import (get_organization_owners_team,
                                    add_user_to_organization)
from onadata.apps.api.models.organization_profile import OrganizationProfile
from rest_framework import status


class TestOrganizationProfileViewSet(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = OrganizationProfileViewSet.as_view({
            'get': 'list',
            'post': 'create',
            'patch': 'partial_update',
        })

    def test_partial_updates(self):
        self._org_create()
        metadata = {u'computer': u'mac'}
        json_metadata = json.dumps(metadata)
        data = {'metadata': json_metadata}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user='denoinc')
        profile = OrganizationProfile.objects.get(name='Dennis')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.metadata, metadata)

    def test_partial_updates_invalid(self):
        self._org_create()
        data = {'name': "a" * 31}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user='denoinc')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['name'],
            [u'Ensure this field has no more than 30 characters.'])

    def test_orgs_list(self):
        self._org_create()
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        del self.company_data['metadata']
        self.assertEqual(response.data, [self.company_data])

        # inactive organization
        self.organization.user.is_active = False
        self.organization.user.save()

        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_orgs_list_for_anonymous_user(self):
        self._org_create()
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_orgs_list_for_authenticated_user(self):
        self._org_create()
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        del self.company_data['metadata']
        self.assertEqual(response.data, [self.company_data])

    def test_orgs_list_shared_with_user(self):
        authenticated_user = self.user
        user_in_shared_organization, _ = User.objects.get_or_create(
            username='the_stalked')

        unshared_organization, _ = User.objects.get_or_create(
            username='NotShared')
        unshared_organization_profile, _ = OrganizationProfile\
            .objects.get_or_create(
                user=unshared_organization,
                creator=authenticated_user)

        add_user_to_organization(unshared_organization_profile,
                                 authenticated_user)

        shared_organization, _ = User.objects.get_or_create(username='Shared')
        shared_organization_profile, _ = OrganizationProfile\
            .objects.get_or_create(
                user=shared_organization,
                creator=user_in_shared_organization)

        add_user_to_organization(shared_organization_profile,
                                 authenticated_user)

        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertTrue(len(response.data), 2)
        request = self.factory.get('/',
                                   data={'shared_with': 'the_stalked'},
                                   **self.extra)
        response = self.view(request)
        self.assertEqual(len(response.data), 1)

    def test_orgs_list_restricted(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'get': 'list'
        })

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)
        self.assertEqual(self.user.username, 'alice')

        request = self.factory.get('/', **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data, [])

    def test_orgs_get(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {'detail': 'Expected URL keyword argument `user`.'})
        request = self.factory.get('/', **self.extra)
        response = view(request, user='denoinc')
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.company_data)
        self.assertIn('users', list(response.data))
        for user in response.data['users']:
            self.assertEqual(user['role'], 'owner')
            self.assertTrue(isinstance(user['user'], text))

    def test_orgs_get_not_creator(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'get': 'retrieve'
        })
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        previous_user = self.user
        self._login_user_and_profile(extra_post_data=alice_data)
        self.assertEqual(self.user.username, 'alice')
        self.assertNotEqual(previous_user, self.user)
        request = self.factory.get('/', **self.extra)
        response = view(request, user='denoinc')
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        del self.company_data['metadata']
        self.assertEqual(response.data, self.company_data)
        self.assertIn('users', list(response.data))
        for user in response.data['users']:
            self.assertEqual(user['role'], 'owner')
            self.assertTrue(isinstance(user['user'], text))

    def test_orgs_get_anon(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/')
        response = view(request, user='denoinc')
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        del self.company_data['metadata']
        self.assertEqual(response.data, self.company_data)
        self.assertIn('users', list(response.data))
        for user in response.data['users']:
            self.assertEqual(user['role'], 'owner')
            self.assertTrue(isinstance(user['user'], text))

    def test_orgs_create(self):
        self._org_create()
        self.assertTrue(self.organization.user.is_active)

    def test_orgs_create_without_name(self):
        data = {
            'org': u'denoinc',
            'city': u'Denoville',
            'country': u'US',
            'home_page': u'deno.com',
            'twitter': u'denoinc',
            'description': u'',
            'address': u'',
            'phonenumber': u'',
            'require_auth': False,
        }
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.data, {'name': [u'This field is required.']})

    def test_org_create_with_anonymous_user(self):
        data = {
            'name': u'denoinc',
            'org': u'denoinc',
            'city': u'Denoville',
            'country': u'US',
            'home_page': u'deno.com',
            'twitter': u'denoinc',
            'description': u'',
            'address': u'',
            'phonenumber': u'',
            'require_auth': False,
        }
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json")
        response = self.view(request)
        self.assertEquals(response.status_code, 401)

    def test_orgs_members_list(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'get': 'members'
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data, [u'denoinc'])

    def test_add_members_to_org_username_required(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })
        request = self.factory.post('/', data={}, **self.extra)
        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data,
                         {u'username': [u"This field may not be null."]})

    def test_add_members_to_org_user_does_not_exist(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })
        data = {'username': 'aboy'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data,
                         {u'username': [u"User 'aboy' does not exist."]})

    def test_add_members_to_org(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })

        self.profile_data['username'] = 'aboy'
        self.profile_data['email'] = 'aboy@org.com'
        self._create_user_profile()
        data = {'username': 'aboy'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set([u'denoinc', u'aboy']))

    def test_add_members_to_org_user_org_account(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })

        username = 'second_inc'

        # Create second org
        org_data = {'org': username}
        self._org_create(org_data=org_data)

        data = {'username': username}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data,
                         {'username': [u'Cannot add org account `second_inc` '
                                       u'as member.']})

    def test_member_sees_orgs_added_to(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'get': 'list',
            'post': 'members'
        })

        member = 'aboy'
        cur_username = self.profile_data['username']
        self.profile_data['username'] = member
        self._login_user_and_profile()
        self.profile_data['username'] = cur_username
        self._login_user_and_profile()

        data = {'username': member}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set([u'denoinc', u'aboy']))

        self.profile_data['username'] = member
        self._login_user_and_profile()

        expected_data = self.company_data
        expected_data['users'].append({
            'first_name': u'Bob',
            'last_name': u'erama',
            'role': 'member',
            'user': member,
            'gravatar': self.user.profile.gravatar,
        })
        del expected_data['metadata']

        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [expected_data])

    def test_role_for_org_non_owner(self):
        # creating org with member
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'get': 'retrieve',
            'post': 'members'
        })

        self.profile_data['username'] = "aboy"
        self._create_user_profile()
        data = {'username': 'aboy'}
        user_role = 'member'
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, user='denoinc')

        # getting profile
        request = self.factory.get('/', **self.extra)
        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)
        self.assertIn('users', list(response.data))

        for user in response.data['users']:
            username = user['user']
            role = user['role']
            expected_role = 'owner' if username == 'denoinc' else user_role
            self.assertEqual(role, expected_role)

    def test_add_members_to_org_with_anonymous_user(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })

        self._create_user_profile(extra_post_data={'username': 'aboy'})
        data = {'username': 'aboy'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json")

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 401)
        self.assertNotEquals(set(response.data), set([u'denoinc', u'aboy']))

    def test_add_members_to_org_with_non_member_user(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })

        self._create_user_profile(extra_post_data={'username': 'aboy'})
        data = {'username': 'aboy'}
        previous_user = self.user
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        self._login_user_and_profile(extra_post_data=alice_data)
        self.assertEqual(self.user.username, 'alice')
        self.assertNotEqual(previous_user,  self.user)
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(set(response.data), set([u'denoinc', u'aboy']))

    def test_remove_members_from_org(self):
        self._org_create()
        newname = 'aboy'
        view = OrganizationProfileViewSet.as_view({
            'post': 'members',
            'delete': 'members'
        })

        self._create_user_profile(extra_post_data={'username': newname})

        data = {'username': newname}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set([u'denoinc', newname]))

        request = self.factory.delete(
            '/', json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [u'denoinc'])

        newname = 'aboy2'
        self._create_user_profile(extra_post_data={'username': newname})

        data = {'username': newname}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set([u'denoinc', newname]))

        request = self.factory.delete(
            '/?username={}'.format(newname), **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [u'denoinc'])

        # Removes users from org projects.
        # Create a project
        project_data = {
            'owner': self.company_data['user']
        }
        self._project_create(project_data)

        # Create alice
        alice = 'alice'
        self._create_user_profile(extra_post_data={'username': alice})
        alice_data = {'username': alice,
                      'role': 'owner'}
        request = self.factory.post(
            '/', data=json.dumps(alice_data),
            content_type="application/json", **self.extra)
        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)

        # alice is in project
        projectView = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = projectView(request, pk=self.project.pk)
        project_users = response.data.get('users')
        users_in_users = [user['user'] for user in project_users]

        self.assertIn(alice, users_in_users)

        # remove alice from org
        request = self.factory.delete(
            '/?username={}'.format(alice), **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(response.data, [u'alice'])

        # alice is also removed from project
        projectView = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = projectView(request, pk=self.project.pk)
        project_users = response.data.get('users')
        users_in_users = [user['user'] for user in project_users]

        self.assertNotIn(alice, users_in_users)

    def test_orgs_create_with_mixed_case(self):
        data = {
            'name': u'denoinc',
            'org': u'DenoINC',
            'city': u'Denoville',
            'country': u'US',
            'home_page': u'deno.com',
            'twitter': u'denoinc',
            'description': u'',
            'address': u'',
            'phonenumber': u'',
            'require_auth': False,
        }
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        data['org'] = 'denoinc'
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Organization %s already exists." % data['org'],
                      response.data['org'])

    def test_publish_xls_form_to_organization_project(self):
        self._org_create()
        project_data = {
            'owner': self.company_data['user']
        }
        self._project_create(project_data)
        self._publish_xls_form_to_project()
        self.assertTrue(OwnerRole.user_has_role(self.user, self.xform))

    def test_put_change_role(self):
        self._org_create()
        newname = 'aboy'
        view = OrganizationProfileViewSet.as_view({
            'get': 'retrieve',
            'post': 'members',
            'put': 'members'
        })

        self.profile_data['username'] = newname
        self._create_user_profile()
        data = {'username': newname}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(sorted(response.data), sorted([u'denoinc', newname]))

        user_role = 'editor'
        data = {'username': newname, 'role': user_role}
        request = self.factory.put(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(response.data), sorted([u'denoinc', newname]))

        # getting profile
        request = self.factory.get('/', **self.extra)
        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)
        self.assertIn('users', list(response.data))

        for user in response.data['users']:
            username = user['user']
            role = user['role']
            expected_role = 'owner' if username == 'denoinc' else user_role
            self.assertEqual(role, expected_role)

    def test_put_require_role(self):
        self._org_create()
        newname = 'aboy'
        view = OrganizationProfileViewSet.as_view({
            'get': 'retrieve',
            'post': 'members',
            'put': 'members'
        })

        self.profile_data['username'] = newname
        self._create_user_profile()
        data = {'username': newname}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set([u'denoinc', newname]))

        data = {'username': newname}
        request = self.factory.put(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 400)

    def test_put_bad_role(self):
        self._org_create()
        newname = 'aboy'
        view = OrganizationProfileViewSet.as_view({
            'get': 'retrieve',
            'post': 'members',
            'put': 'members'
        })

        self.profile_data['username'] = newname
        self._create_user_profile()
        data = {'username': newname}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set([u'denoinc', newname]))

        data = {'username': newname, 'role': 42}
        request = self.factory.put(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 400)

    @patch('onadata.libs.serializers.organization_member_serializer.send_mail')
    def test_add_members_to_org_email(self, mock_email):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })

        self.profile_data['username'] = 'aboy'
        self.profile_data['email'] = 'aboy@org.com'
        self._create_user_profile()
        data = {'username': 'aboy',
                'email_msg': 'You have been add to denoinc'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(mock_email.called)
        mock_email.assert_called_with('aboy, You have been added to Dennis'
                                      ' organisation.',
                                      u'You have been add to denoinc',
                                      'noreply@ona.io',
                                      (u'aboy@org.com',))
        self.assertEqual(set(response.data), set([u'denoinc', u'aboy']))

    @patch('onadata.libs.serializers.organization_member_serializer.send_mail')
    def test_add_members_to_org_email_custom_subj(self, mock_email):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })

        self.profile_data['username'] = 'aboy'
        self.profile_data['email'] = 'aboy@org.com'
        self._create_user_profile()
        data = {'username': 'aboy',
                'email_msg': 'You have been add to denoinc',
                'email_subject': 'Your are made'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(mock_email.called)
        mock_email.assert_called_with('Your are made',
                                      u'You have been add to denoinc',
                                      'noreply@ona.io',
                                      (u'aboy@org.com',))
        self.assertEqual(set(response.data), set([u'denoinc', u'aboy']))

    def test_add_members_to_org_with_role(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members',
            'get': 'retrieve'
        })

        self.profile_data['username'] = "aboy"
        self._create_user_profile()
        data = {'username': 'aboy',
                'role': 'editor'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)

        self.assertEqual(set(response.data), set([u'denoinc', u'aboy']))

        # getting profile
        request = self.factory.get('/', **self.extra)
        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['users'][1]['user'], 'aboy')
        self.assertEqual(response.data['users'][1]['role'], 'editor')

    def test_add_members_to_owner_role(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members',
            'get': 'retrieve',
            'put': 'members'
        })

        self.profile_data['username'] = "aboy"
        aboy = self._create_user_profile().user

        data = {'username': 'aboy',
                'role': 'owner'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)

        self.assertEqual(set(response.data), set([u'denoinc', u'aboy']))

        # getting profile
        request = self.factory.get('/', **self.extra)
        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['users'][1]['user'], 'aboy')
        self.assertEqual(response.data['users'][1]['role'], 'owner')

        owner_team = get_organization_owners_team(self.organization)

        self.assertIn(aboy, owner_team.user_set.all())

        # test user removed from owner team when role changed
        data = {'username': 'aboy', 'role': 'editor'}
        request = self.factory.put(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)

        owner_team = get_organization_owners_team(self.organization)

        self.assertNotIn(aboy, owner_team.user_set.all())

    def test_org_members_added_to_projects(self):
        # create org
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members',
            'get': 'retrieve',
            'put': 'members'
        })

        # create aboy
        self.profile_data['username'] = "aboy"
        aboy = self._create_user_profile().user

        data = {'username': 'aboy',
                'role': 'owner'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)

        # create a proj
        project_data = {
            'owner': self.company_data['user']
        }
        self._project_create(project_data)
        self._publish_xls_form_to_project()

        # create alice
        self.profile_data['username'] = "alice"
        alice = self._create_user_profile().user
        alice_data = {'username': 'alice',
                      'role': 'owner'}
        request = self.factory.post(
            '/', data=json.dumps(alice_data),
            content_type="application/json", **self.extra)
        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)

        # Assert that user added in org is added to teams in proj
        self.assertTrue(OwnerRole.user_has_role(aboy, self.project))
        self.assertTrue(OwnerRole.user_has_role(alice, self.project))
        self.assertTrue(OwnerRole.user_has_role(aboy, self.xform))
        self.assertTrue(OwnerRole.user_has_role(alice, self.xform))

        # Org admins are added to owners in project
        projectView = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = projectView(request, pk=self.project.pk)
        project_users = response.data.get('users')
        users_in_users = [user['user'] for user in project_users]

        self.assertIn('bob', users_in_users)
        self.assertIn('denoinc', users_in_users)
        self.assertIn('aboy', users_in_users)
        self.assertIn('alice', users_in_users)

    def test_put_role_user_none_existent(self):
        self._org_create()
        newname = 'i-do-no-exist'
        view = OrganizationProfileViewSet.as_view({
            'get': 'retrieve',
            'post': 'members',
            'put': 'members'
        })

        data = {'username': newname, 'role': 'editor'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 400)

    def test_update_org_name(self):
        self._org_create()

        # update name
        data = {'name': "Dennis2"}
        request = self.factory.patch('/', data=data, **self.extra)
        response = self.view(request, user='denoinc')
        self.assertEqual(response.data['name'], "Dennis2")
        self.assertEqual(response.status_code, 200)

        # check in user profile endpoint
        view_user = UserProfileViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)

        response = view_user(request, user='denoinc')
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], "Dennis2")

    def test_org_always_has_admin_or_owner(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'put': 'members',
        })
        data = {'username': self.user.username, 'role': 'editor'}
        request = self.factory.put(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 400)
        self.assertEquals(response.data,
                          {
                              u'non_field_errors':
                                  [u'Organization cannot be without an owner']
                          })

    def test_owner_not_allowed_to_be_removed(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members',
            'delete': 'members',
            'get': 'retrieve',
        })

        self.profile_data['username'] = "aboy"
        aboy = self._create_user_profile().user

        data = {'username': aboy.username,
                'role': 'owner'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set([u'denoinc',
                                                  aboy.username]))

        self.profile_data['username'] = "aboy2"
        aboy2 = self._create_user_profile().user

        data = {'username': aboy2.username,
                'role': 'owner'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set([u'denoinc',
                                                  aboy.username,
                                                  aboy2.username]))

        data = {'username': aboy2.username}
        request = self.factory.delete(
            '/', json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)
        for user in [u'denoinc', aboy.username]:
            self.assertIn(user, response.data)

        # at this point we have bob and aboy as owners
        data = {'username': aboy.username}
        request = self.factory.delete(
            '/', json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)

        # at this point we only have bob as the owner
        data = {'username': self.user.username}
        request = self.factory.delete(
            '/', json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 400)
        self.assertEquals(response.data,
                          {
                              u'non_field_errors':
                                  [u'Organization cannot be without an owner']
                          })

    def test_orgs_delete(self):
        self._org_create()
        self.assertTrue(self.organization.user.is_active)

        view = OrganizationProfileViewSet.as_view({
            'delete': 'destroy'
        })

        request = self.factory.delete('/', **self.extra)
        response = view(request, user='denoinc')

        self.assertEquals(204, response.status_code)

        self.assertEquals(0, OrganizationProfile.objects.filter(
            user__username='denoinc').count())
        self.assertEquals(0, User.objects.filter(username='denoinc').count())

    def test_orgs_non_creator_delete(self):
        self._org_create()

        view = OrganizationProfileViewSet.as_view({
            'delete': 'members',
            'post': 'members'
        })

        self.profile_data['username'] = "alice"
        self.profile_data['email'] = 'alice@localhost.com'
        self._create_user_profile()

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        request = self.factory.post(
            '/', data=json.dumps(alice_data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        expected_results = [u'denoinc', u'alice']
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(expected_results, response.data)

        self._login_user_and_profile(extra_post_data=alice_data)

        request = self.factory.delete('/', data=json.dumps(alice_data),
                                      content_type="application/json",
                                      **self.extra)
        response = view(request, user='denoinc')
        expected_results = [u'denoinc']
        self.assertEqual(expected_results, response.data)
