from django_digest.test import DigestAuth, BasicAuth
from rest_framework import authentication

from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet

from onadata.libs.authentication import DigestAuthentication
from onadata.libs.serializers.project_serializer import ProjectSerializer


class TestConnectViewSet(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = ConnectViewSet.as_view({
            "get": "list"
        })
        self.data = {
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
            'user': 'http://testserver/api/v1/users/bob',
            'api_token': self.user.auth_token.key,
            'temp_token': self.client.session.session_key
        }

    def test_get_profile(self):
        request = self.factory.get('/', **self.extra)
        request.session = self.client.session

        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

    def test_get_starred_projects(self):
        self._project_create()

        # add star as bob
        view = ProjectViewSet.as_view({
            'get': 'star',
            'post': 'star'
        })
        request = self.factory.post('/', **self.extra)
        response = view(request, pk=self.project.pk)

        # get starred projects
        view = ConnectViewSet.as_view({
            'get': 'starred',
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, user=self.user)

        self.assertEqual(response.status_code, 200)

        request.user = self.user
        self.project_data = ProjectSerializer(
            self.project, context={'request': request}).data
        self.assertEqual(response.data, [self.project_data])

    def test_user_list_with_digest(self):
        view = ConnectViewSet.as_view(
            {'get': 'list'},
            authentication_classes=(DigestAuthentication,))
        request = self.factory.head('/')

        auth = DigestAuth('bob', 'bob')
        response = view(request)
        self.assertTrue(response.has_header('WWW-Authenticate'))
        self.assertTrue(
            response['WWW-Authenticate'].startswith('Digest nonce='))
        request = self.factory.get('/')
        request.META.update(auth(request.META, response))
        request.session = self.client.session

        response = view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['detail'],
                         u"Invalid username/password")
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        request.session = self.client.session

        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

    def test_user_list_with_basic_and_digest(self):
        view = ConnectViewSet.as_view(
            {'get': 'list'},
            authentication_classes=(
                DigestAuthentication,
                authentication.BasicAuthentication
            ))
        request = self.factory.get('/')
        auth = BasicAuth('bob', 'bob')
        request.META.update(auth(request.META))
        request.session = self.client.session

        response = view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['detail'],
                         u"Invalid username/password")
        auth = BasicAuth('bob', 'bobbob')
        request.META.update(auth(request.META))
        request.session = self.client.session

        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)
