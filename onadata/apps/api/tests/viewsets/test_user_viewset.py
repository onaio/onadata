from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.user_viewset import UserViewSet


class TestUserViewSet(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.data = {'id': self.user.pk, 'username': u'bob',
                     'first_name': u'Bob', 'last_name': u''}

    def test_user_get(self):
        """Test authenticated user can access user info"""
        request = self.factory.get('/', **self.extra)

        # users list
        view = UserViewSet.as_view({'get': 'list'})
        response = view(request)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.data])

        # user with username bob
        view = UserViewSet.as_view({'get': 'retrieve'})
        response = view(request, username='bob')
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

    def test_user_anon(self):
        """Test anonymous user can access user info"""
        request = self.factory.get('/')

        # users list endpoint
        view = UserViewSet.as_view({'get': 'list'})
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.data])

        # user with username bob
        view = UserViewSet.as_view({'get': 'retrieve'})
        response = view(request, username='bob')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

        # Test with primary key
        response = view(request, username=self.user.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

    def test_get_user_using_email(self):
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com',
                      'name': u'Alice'}
        alice_profile = self._create_user_profile(alice_data)
        data = {'id': alice_profile.user.pk, 'username': u'alice',
                'first_name': u'Alice', 'last_name': u''}
        get_params = {
            'email': alice_profile.user.email,
        }
        view = UserViewSet.as_view(
            {'get': 'list'}
        )
        request = self.factory.get('/', data=get_params)

        response = view(request)
        self.assertEquals(response.status_code, 401)
        error = {'detail': 'Authentication credentials were not provided.'}
        self.assertEqual(response.data, error)

        # authenticated
        request = self.factory.get('/', data=get_params, **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 200)
        self.assertEqual(response.data, data)

        get_params = {
            'email': 'invalidemail',
        }

        request = self.factory.get('/', data=get_params, **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.data, {'details': 'Invalid email'})

        get_params = {
            'email': 'doesnotexist@email.com',
        }

        request = self.factory.get('/', data=get_params, **self.extra)
        response = view(request)
        self.assertEquals(response.status_code, 404)
        self.assertEquals(response.data, {'detail': 'User not found'})
