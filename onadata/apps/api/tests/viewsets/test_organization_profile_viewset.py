import json

from django.contrib.auth.models import User

from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.organization_profile_viewset import\
    OrganizationProfileViewSet
from onadata.libs.permissions import OwnerRole


class TestOrganizationProfileViewSet(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = OrganizationProfileViewSet.as_view({
            'get': 'list',
            'post': 'create'
        })

    def test_orgs_list(self):
        self._org_create()
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.company_data])

    def test_orgs_list_for_anonymous_user(self):
        self._org_create()
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data,
            {u'detail': u'Authentication credentials were not provided.'})

    def test_orgs_list_for_authenticated_user(self):
        self._org_create()
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.company_data])

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
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.company_data)
        self.assertIn('users', response.data.keys())
        for user in response.data['users']:
            self.assertEqual(user['role'], 'owner')
            self.assertEqual(type(user['user']), unicode)

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
        self.assertContains(response, '{"name": "name is required!"}',
                            status_code=400)

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
                         {u'username': [u"This field is required."]})

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
                         {u'username': [u"User `aboy` does not exist."]})

    def test_add_members_to_org(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })

        User.objects.create(username='aboy')
        data = {'username': 'aboy'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'denoinc', u'aboy'])

    def test_member_sees_orgs_added_to(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'get': 'list',
            'post': 'members'
        })

        member = 'aboy'
        expected_data = self.company_data
        expected_data['users'].append({'role': 'member', 'user': member})
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
        self.assertEqual(response.data, [u'denoinc', u'aboy'])

        self.profile_data['username'] = member
        self._login_user_and_profile()

        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [expected_data])

    def test_role_for_org_non_owner(self):
        # creating org with member
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })

        User.objects.create(username='aboy')
        data = {'username': 'aboy'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, user='denoinc')

        # getting profile
        view = OrganizationProfileViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 200)
        self.assertIn('users', response.data.keys())

        for user in response.data['users']:
            username = user['user']
            role = 'owner' if username == 'denoinc' else 'member'
            if username == 'denoinc':
                self.assertEqual(role, 'owner')
            else:
                self.assertEqual(role, 'member')

    def test_add_members_to_org_with_anonymous_user(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })

        User.objects.create(username='aboy')
        data = {'username': 'aboy'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json")

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 401)
        self.assertNotEquals(response.data, [u'denoinc', u'aboy'])

    def test_add_members_to_org_with_non_member_user(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })

        User.objects.create(username='aboy', )
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
        self.assertNotEqual(response.data, [u'denoinc', u'aboy'])

    def test_remove_members_from_org(self):
        self._org_create()
        newname = 'aboy'
        view = OrganizationProfileViewSet.as_view({
            'post': 'members',
            'delete': 'members'
        })

        User.objects.create(username=newname)
        data = {'username': newname}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'denoinc', newname])

        request = self.factory.delete(
            '/', json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user='denoinc')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'denoinc'])

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
        self.assertIn("%s already exists" % data['org'], response.data['org'])

    def test_publish_xls_form_to_organization_project(self):
        self._org_create()
        project_data = {
            'owner':  self.company_data['user']
        }
        self._project_create(project_data)
        self._publish_xls_form_to_project()
        self.assertTrue(OwnerRole.user_has_role(self.user, self.xform))
