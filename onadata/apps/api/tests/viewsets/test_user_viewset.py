import json

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
        # users list
        view = UserViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.data])

        # user with username bob
        view = UserViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/', **self.extra)
        response = view(request, username='bob')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

    def test_user_anon(self):
        """Test anonymous user can access user info"""
        # users list endpoint
        view = UserViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.data])

        # user with username bob
        view = UserViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/')
        response = view(request, username='bob')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)
