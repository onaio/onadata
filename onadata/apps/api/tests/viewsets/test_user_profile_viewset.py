import json

from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.apps.main.models import UserProfile


class TestUserProfileViewSet(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = UserProfileViewSet.as_view({
            'get': 'list',
            'post': 'create'
        })

    def test_profiles_list(self):
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        data = [
            {
                'url': 'http://testserver/api/v1/profiles/bob',
                'username': u'bob',
                'name': u'Bob',
                'email': u'bob@columbia.edu',
                'city': u'Bobville',
                'country': u'US',
                'organization': u'Bob Inc.',
                'website': u'bob.com',
                'twitter': u'boberama',
                'gravatar': self.user.profile.gravatar,
                'require_auth': False,
                'user': 'http://testserver/api/v1/users/bob'
            }
        ]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_profiles_get(self):
        view = UserProfileViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {'detail': 'Expected URL keyword argument `user`.'})
        request = self.factory.get('/', **self.extra)
        response = view(request, user='bob')
        data = {
            'url': 'http://testserver/api/v1/profiles/bob',
            'username': u'bob',
            'name': u'Bob',
            'email': u'bob@columbia.edu',
            'city': u'Bobville',
            'country': u'US',
            'organization': u'Bob Inc.',
            'website': u'bob.com',
            'twitter': u'boberama',
            'gravatar': self.user.profile.gravatar,
            'require_auth': False,
            'user': 'http://testserver/api/v1/users/bob'
        }
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_profile_create(self):
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = {
            'username': u'deno',
            'name': u'Dennis',
            'email': u'deno@columbia.edu',
            'city': u'Denoville',
            'country': u'US',
            'organization': u'Dono Inc.',
            'website': u'deno.com',
            'twitter': u'denoerama',
            'require_auth': False,
            'password': 'denodeno',
        }
        # response = self.client.post(
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        del data['password']
        profile = UserProfile.objects.get(user__username=data['username'])
        data['gravatar'] = profile.gravatar
        data['url'] = 'http://testserver/api/v1/profiles/deno'
        data['user'] = 'http://testserver/api/v1/users/deno'
        self.assertEqual(response.data, data)

    def test_profile_create_missing_name_field(self):
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = {
            'username': u'deno',
            'email': u'deno@columbia.edu',
            'city': u'Denoville',
            'country': u'US',
            'organization': u'Dono Inc.',
            'website': u'deno.com',
            'twitter': u'denoerama',
            'require_auth': False,
            'password': 'denodeno',
        }
        # response = self.client.post(
        request = self.factory.post(
            '/api/v1/profiles', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        response.render()
        self.assertContains(response, '{"name": ["This field is required."]}',
                            status_code=400)
