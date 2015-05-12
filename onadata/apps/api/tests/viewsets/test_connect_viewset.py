from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.timezone import now
from django_digest.test import DigestAuth, BasicAuth
from mock import patch
from datetime import timedelta
from rest_framework import authentication
from rest_framework.authtoken.models import Token

from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet

from onadata.libs.authentication import DigestAuthentication
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.apps.api.models.temp_token import TempToken
from django.conf import settings


class TestConnectViewSet(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = ConnectViewSet.as_view({
            "get": "list",
            "post": "reset",
            "delete": "expire"
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
        }

    def test_regenerate_auth_token(self):
        self.view = ConnectViewSet.as_view({
            "get": "regenerate_auth_token",
            })
        prev_token = self.user.auth_token
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        new_token = Token.objects.get(user=self.user)
        self.assertNotEqual(prev_token, new_token)

        self.view = ConnectViewSet.as_view({
            "get": "list",
            })
        self.extra = {'HTTP_AUTHORIZATION': 'Token %s' % new_token}
        request = self.factory.get('/', **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

    def test_get_profile(self):
        request = self.factory.get('/', **self.extra)
        request.session = self.client.session
        response = self.view(request)
        temp_token = TempToken.objects.get(user__username='bob')
        self.data['temp_token'] = temp_token.key
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)

    def test_using_valid_temp_token(self):
        request = self.factory.get('/', **self.extra)
        request.session = self.client.session
        response = self.view(request)
        temp_token = response.data['temp_token']

        self.extra = {'HTTP_AUTHORIZATION': 'TempToken %s' % temp_token}
        request = self.factory.get('/', **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(temp_token, response.data['temp_token'])

    def test_using_invalid_temp_token(self):
        request = self.factory.get('/', **self.extra)
        request.session = self.client.session
        response = self.view(request)
        temp_token = 'abcdefghijklmopqrstuvwxyz'

        self.extra = {'HTTP_AUTHORIZATION': 'TempToken %s' % temp_token}
        request = self.factory.get('/', **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['detail'], 'Invalid token')

    def test_using_expired_temp_token(self):
        request = self.factory.get('/', **self.extra)
        request.session = self.client.session
        response = self.view(request)
        temp_token = response.data['temp_token']
        temp_token_obj = TempToken.objects.get(key=temp_token)

        day = timedelta(seconds=settings.DEFAULT_TEMP_TOKEN_EXPIRY_TIME)
        today = now()
        yesterday = today - day
        temp_token_obj.created = yesterday
        temp_token_obj.save()

        self.extra = {'HTTP_AUTHORIZATION': 'TempToken %s' %
                      temp_token_obj.key}
        request = self.factory.get('/', **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.data['detail'], 'Token expired')

    def test_expire_temp_token_using_expire_endpoint(self):
        request = self.factory.get('/', **self.extra)
        request.session = self.client.session
        response = self.view(request)
        temp_token = response.data['temp_token']

        # expire temporary token
        request = self.factory.delete('/', **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 204)

        # try to expire temporary token for the second time
        request = self.factory.delete('/', **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'Temporary token not found!')

        # try to login with deleted temporary token
        self.extra = {'HTTP_AUTHORIZATION': 'TempToken %s' % temp_token}
        request = self.factory.get('/', **self.extra)
        request.session = self.client.session
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['detail'],
                         'Invalid token')

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
        temp_token = TempToken.objects.get(user__username='bob')
        self.data['temp_token'] = temp_token.key
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
        temp_token = TempToken.objects.get(user__username='bob')
        self.data['temp_token'] = temp_token.key
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

    @patch('onadata.libs.serializers.password_reset_serializer.send_mail')
    def test_request_reset_password_custom_email_subject(self, mock_send_mail):
        data = {'email': self.user.email,
                'reset_url': u'http://testdomain.com/reset_form',
                'email_subject': 'You requested for a reset password'}
        request = self.factory.post('/', data=data)
        response = self.view(request)

        self.assertTrue(mock_send_mail.called)
        self.assertEqual(response.status_code, 204)

        mock_send_mail.called = False
        request = self.factory.post('/')
        response = self.view(request)
        self.assertFalse(mock_send_mail.called)
        self.assertEqual(response.status_code, 400)
