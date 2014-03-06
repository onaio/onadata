from onadata.apps.logger.views import formList
from django.core.urlresolvers import reverse
from onadata.apps.main.models import UserProfile
from django_digest.test import Client as DigestClient
from onadata.apps.main.tests.test_base import TestBase


class TestFormList(TestBase):
    def setUp(self):
        super(TestFormList, self).setUp()
        self.profile = UserProfile.objects.create(
            user=self.user, require_auth=True)
        self.profile.save()
        self.digest_client = DigestClient()

    def test_returns_200_for_owner(self):
        self.digest_client.set_authorization('bob', 'bob')
        response = self.digest_client.get(reverse(formList, kwargs={
            'username': 'bob'
        }))
        self.assertEqual(response.status_code, 200)

    def test_returns_401_for_anon(self):
        response = self.anon.get(reverse(formList, kwargs={
            'username': 'bob'
        }))
        self.assertEqual(response.status_code, 401)

    def test_returns_200_for_authenticated_non_owner(self):
        credentials = ('alice', 'alice',)
        self._create_user(*credentials)
        self.digest_client.set_authorization(*credentials)
        response = self.digest_client.get(reverse(formList, kwargs={
            'username': 'bob'
        }))
        self.assertEqual(response.status_code, 200)
