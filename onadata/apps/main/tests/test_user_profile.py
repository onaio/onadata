from django.test import TestCase
from django.test import RequestFactory
from django.test.client import Client
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.contrib.auth.models import AnonymousUser

from onadata.apps.main.views import profile, api_token


class TestUserProfile(TestCase):

    def setup(self):
        self.client = Client()
        self.assertEqual(len(User.objects.all()), 0)

    def _login_user_and_profile(self, extra_post_data={}):
        post_data = {
            'username': 'bob',
            'email': 'bob@columbia.edu',
            'password1': 'bobbob',
            'password2': 'bobbob',
            'first_name': 'Bob',
            'last_name': 'User',
            'city': 'Bobville',
            'country': 'US',
            'organization': 'Bob Inc.',
            'home_page': 'bob.com',
            'twitter': 'boberama'
        }
        url = '/accounts/register/'
        post_data = dict(post_data.items() + extra_post_data.items())
        self.response = self.client.post(url, post_data)
        try:
            self.user = User.objects.get(username=post_data['username'])
        except User.DoesNotExist:
            pass

    def test_create_user_with_given_name(self):
        self._login_user_and_profile()
        self.assertEqual(self.response.status_code, 302)
        self.assertEqual(self.user.username, 'bob')

    def test_create_user_profile_for_user(self):
        self._login_user_and_profile()
        self.assertEqual(self.response.status_code, 302)
        user_profile = self.user.profile
        self.assertEqual(user_profile.city, 'Bobville')
        self.assertTrue(hasattr(user_profile, 'metadata'))

    def test_disallow_non_alpha_numeric(self):
        invalid_usernames = [
            'b ob',
            'b.o.b.',
            'b-ob',
            'b!',
            '@bob',
            'bob@bob.com',
            'bob$',
            'b&o&b',
            'bob?',
            '#bob',
            '(bob)',
            'b*ob',
            '%s % bob',
        ]
        users_before = User.objects.count()
        for username in invalid_usernames:
            self._login_user_and_profile({'username': username})
            self.assertEqual(User.objects.count(), users_before)

    def test_disallow_reserved_name(self):
        users_before = User.objects.count()
        self._login_user_and_profile({'username': 'admin'})
        self.assertEqual(User.objects.count(), users_before)

    def test_404_if_user_does_not_exist(self):
        response = self.client.get(reverse(profile,
                                           kwargs={'username': 'nonuser'}))
        self.assertEqual(response.status_code, 404)

    def test_403_if_unauthorised_user_tries_to_access_api_token_link(self):
        # try accessing with unauthorised user
        factory = RequestFactory()

        # create user alice
        post_data = {
            'username': 'alice',
            'email': 'alice@columbia.edu',
            'password1': 'alicealice',
            'password2': 'alicealice',
            'first_name': 'Alice',
            'last_name': 'Wonderland',
            'city': 'Aliceville',
            'country': 'KE',
            'organization': 'Alice Inc.',
            'home_page': 'alice.com',
            'twitter': 'alicemsweet'
        }
        url = '/accounts/register/'
        self.client.post(url, post_data)

        # try accessing api-token with an anonymous user
        request = factory.get('/api-token')
        request.user = AnonymousUser()
        response = api_token(request, 'alice')
        self.assertEqual(response.status_code, 302)

        # login with user bob
        self._login_user_and_profile()

        # try accessing api-token with user 'bob' but with username 'alice'
        request = factory.get('/api-token')
        request.user = self.user
        response = api_token(request, 'alice')
        self.assertEqual(response.status_code, 403)

        # try accessing api-token with user 'bob' but with username 'bob'
        request = factory.get('/api-token')
        request.user = self.user
        response = api_token(request, self.user.username)
        self.assertEqual(response.status_code, 200)

    def test_show_single_at_sign_in_twitter_link(self):
        self._login_user_and_profile()
        response = self.client.get(
            reverse(profile, kwargs={
                'username': "bob"
            }))
        self.assertContains(response, ">@boberama")
        # add the @ sign
        self.user.profile.twitter = "@boberama"
        self.user.profile.save()
        response = self.client.get(
            reverse(profile, kwargs={
                'username': "bob"
            }))
        self.assertContains(response, ">@boberama")
