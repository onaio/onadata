from onadata.apps.logger.views import formList
from onadata.apps.main.models import UserProfile
from django.test import RequestFactory
from django_digest.test import DigestAuth
from onadata.apps.main.tests.test_base import TestBase


class TestFormList(TestBase):
    def setUp(self):
        super(TestFormList, self).setUp()
        self.profile = UserProfile.objects.create(
            user=self.user, require_auth=True)
        self.profile.save()
        self.factory = RequestFactory()

    def test_returns_200_for_owner(self):
        request = self.factory.get('/')
        auth = DigestAuth('bob', 'bob')
        response = formList(request, self.user.username)
        request.META.update(auth(request.META, response))
        response = formList(request, self.user.username)
        self.assertEqual(response.status_code, 200)

    def test_returns_401_for_anon(self):
        request = self.factory.get('/')
        response = formList(request, self.user.username)
        self.assertEqual(response.status_code, 401)

    def test_returns_200_for_authenticated_non_owner(self):
        credentials = ('alice', 'alice',)
        self._create_user(*credentials)
        auth = DigestAuth('alice', 'alice')
        request = self.factory.get('/')
        response = formList(request, self.user.username)
        request.META.update(auth(request.META, response))
        response = formList(request, self.user.username)
        self.assertEqual(response.status_code, 200)
