from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from onadata.apps.api.models.temp_token import TempToken

from onadata.libs.authentication import (DigestAuthentication,
                                         TempTokenAuthentication,
                                         TempTokenURLParameterAuthentication)
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory


class TestPermissions(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.extra = {'HTTP_AUTHORIZATION': b'digest &#x0030;'}

    def test_invalid_bytes_in_digest(self):
        digest_auth = DigestAuthentication()
        request = self.factory.get('/', **self.extra)
        self.assertRaises(AuthenticationFailed,
                          digest_auth.authenticate, request)


class TestTempTokenAuthentication(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.temp_token_authentication = TempTokenAuthentication()

    def test_expired_temp_token(self):
        validity_period = getattr(settings, 'DEFAULT_TEMP_TOKEN_EXPIRY_TIME')
        time_to_subtract = validity_period + 1
        user, created = User.objects.get_or_create(username='temp')
        temp_token, created = TempToken.objects.get_or_create(user=user)
        expired_time = temp_token.created - timedelta(seconds=time_to_subtract)
        temp_token.created = expired_time

        temp_token.save()
        self.assertRaisesMessage(
            AuthenticationFailed,
            u'Token expired',
            self.temp_token_authentication.authenticate_credentials,
            temp_token.key)

    def test_inactive_user(self):
        user, created = User.objects.get_or_create(username='temp')
        temp_token, created = TempToken.objects.get_or_create(user=user)
        user.is_active = False
        user.save()
        self.assertRaisesMessage(
            AuthenticationFailed,
            u'User inactive or deleted',
            self.temp_token_authentication.authenticate_credentials,
            temp_token.key)

    def test_invalid_temp_token(self):
        self.assertRaisesMessage(
            AuthenticationFailed,
            u'Invalid token',
            self.temp_token_authentication.authenticate_credentials,
            '123')

    def test_authenticates_if_token_is_valid(self):
        user, created = User.objects.get_or_create(username='temp')
        token, created = TempToken.objects.get_or_create(user=user)

        returned_user, returned_token = self.\
            temp_token_authentication.\
            authenticate_credentials(token.key)
        self.assertEquals(user, returned_user)
        self.assertEquals(token, returned_token)


class TestTempTokenURLParameterAuthentication(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_returns_false_if_no_param(self):
        temp_token_param_authentication = TempTokenURLParameterAuthentication()
        request = self.factory.get('/export/123')
        self.assertEqual(temp_token_param_authentication.authenticate(request),
                         None)
