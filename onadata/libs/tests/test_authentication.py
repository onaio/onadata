from django.test import TestCase
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from onadata.libs.authentication import DigestAuthentication


class TestPermissions(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.extra = {'HTTP_AUTHORIZATION': 'digest &#x0030;'}

    def test_invalid_bytes_in_digest(self):
        digest_auth = DigestAuthentication()
        request = self.factory.get('/', **self.extra)
        self.assertRaises(AuthenticationFailed,
                          digest_auth.authenticate, request)
