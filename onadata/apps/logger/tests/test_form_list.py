from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django_digest.test import DigestAuth

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.views import formList


class TestFormList(TestBase):
    def setUp(self):
        super(TestFormList, self).setUp()
        self.factory = RequestFactory()

    def test_returns_200_for_owner(self):
        self._set_require_auth()
        request = self.factory.get('/')
        auth = DigestAuth('bob', 'bob')
        response = formList(request, self.user.username)
        request.META.update(auth(request.META, response))
        response = formList(request, self.user.username)
        self.assertEqual(response.status_code, 200)

    def test_return_401_for_anon_when_require_auth_true(self):
        self._set_require_auth()
        request = self.factory.get('/')
        response = formList(request, self.user.username)
        self.assertEqual(response.status_code, 401)

    def test_returns_200_for_authenticated_non_owner(self):
        self._set_require_auth()
        credentials = ('alice', 'alice',)
        self._create_user(*credentials)
        auth = DigestAuth('alice', 'alice')
        request = self.factory.get('/')
        response = formList(request, self.user.username)
        request.META.update(auth(request.META, response))
        response = formList(request, self.user.username)
        self.assertEqual(response.status_code, 200)

    def test_show_for_anon_when_require_auth_false(self):
        request = self.factory.get('/')
        request.user = AnonymousUser()
        response = formList(request, self.user.username)
        self.assertEquals(response.status_code, 200)
