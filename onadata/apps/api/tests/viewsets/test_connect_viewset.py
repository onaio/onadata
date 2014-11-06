from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.timezone import now
from django_digest.test import DigestAuth, BasicAuth
from mock import patch
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
            "get": "list",
            "post": "reset"
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

    @patch('onadata.libs.serializers.password_reset_serializer.send_mail')
    def test_request_reset_password(self, mock_send_mail):
        data = {'email': self.user.email,
                'reset_url': u'http://testdomain.com/reset_form'}
        request = self.factory.post('/', data=data)
        response = self.view(request)
        self.assertTrue(mock_send_mail.called)
        self.assertEqual(response.status_code, 204)

        mock_send_mail.called = False
        request = self.factory.post('/')
        response = self.view(request)
        self.assertFalse(mock_send_mail.called)
        self.assertEqual(response.status_code, 400)

    def test_reset_user_password(self):
        # set user.last_login, ensures we get same/valid token
        # https://code.djangoproject.com/ticket/10265
        self.user.last_login = now()
        self.user.save()
        token = default_token_generator.make_token(self.user)
        new_password = "bobbob1"
        data = {'token': token, 'new_password': new_password}
        # missing uid, should fail
        request = self.factory.post('/', data=data)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)

        data['uid'] = urlsafe_base64_encode(force_bytes(self.user.pk))
        # with uid, should be successful
        request = self.factory.post('/', data=data)
        response = self.view(request)
        self.assertEqual(response.status_code, 204)
        user = User.objects.get(email=self.user.email)
        self.assertTrue(user.check_password(new_password))

        request = self.factory.post('/', data=data)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
