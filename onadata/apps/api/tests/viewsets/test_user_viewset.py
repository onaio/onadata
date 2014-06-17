import json

from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.user_viewset import UserViewSet


class TestUserViewSet(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()

    def test_user_list(self):
        view = UserViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        data = [{'username': u'bob', 'first_name': u'Bob', 'last_name': u''}]
        self.assertContains(response, json.dumps(data))

    def test_user_list_anon(self):
        view = UserViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        response = view(request)
        data = [{'username': u'bob', 'first_name': u'Bob', 'last_name': u''}]
        self.assertContains(response, json.dumps(data))

    def test_user_get(self):
        view = UserViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/', **self.extra)
        response = view(request, username='bob')
        data = {'username': u'bob', 'first_name': u'Bob', 'last_name': u''}
        self.assertContains(response, json.dumps(data))

    def test_user_anon_get(self):
        view = UserViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/')
        response = view(request, username='bob')
        data = {'username': u'bob', 'first_name': u'Bob', 'last_name': u''}
        self.assertContains(response, json.dumps(data))
