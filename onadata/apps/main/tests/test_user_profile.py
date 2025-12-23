# -*- coding: utf-8 -*-
"""
Test user profile
"""

from __future__ import unicode_literals

from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch

from onadata.apps.logger.xform_instance_parser import XLSFormError
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.views import api_token, profile
from onadata.libs.utils.common_tools import merge_dicts


class TestUserProfile(TestBase):
    """
    Test user profile
    """

    def setUp(self):
        TestBase.setUp(self)

    def _login_user_and_profile(self, extra_post_data={}):
        # Log out first since TestBase.setUp logs in as 'bob'
        self.client.logout()

        post_data = {
            "username": "testuser",
            "email": "testuser@columbia.edu",
            "password1": "bobbob102011",
            "password2": "bobbob102011",
            "first_name": "Bob",
            "last_name": "User",
            "city": "Bobville",
            "country": "US",
            "organization": "Bob Inc.",
            "home_page": "bob.com",
            "twitter": "boberama",
        }
        url = "/accounts/register/"
        post_data = merge_dicts(post_data, extra_post_data)
        self.response = self.client.post(url, post_data)
        try:
            self.user = User.objects.get(username=post_data["username"])
        except User.DoesNotExist:
            pass

    def test_create_user_with_given_name(self):
        self._login_user_and_profile()
        self.assertEqual(self.response.status_code, 302)
        self.assertEqual(self.user.username, "testuser")

    @patch("onadata.apps.main.views.render")
    def test_xlsform_error_returns_400(self, mock_render):
        mock_render.side_effect = XLSFormError("Title shouldn't have an ampersand")
        self._login_user_and_profile()
        response = self.client.get(reverse(profile, kwargs={"username": "testuser"}))

        self.assertTrue(mock_render.called)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.content.decode("utf-8"), "Title shouldn't have an ampersand"
        )

    def test_create_user_profile_for_user(self):
        self._login_user_and_profile()
        self.assertEqual(self.response.status_code, 302)
        user_profile = self.user.profile
        self.assertEqual(user_profile.city, "Bobville")
        self.assertTrue(hasattr(user_profile, "metadata"))

    def test_disallow_invalid_usernames(self):
        """Test that usernames with forward slashes or blocked file extensions are rejected"""
        invalid_usernames = [
            # Special characters (dots, hyphens, underscores are allowed)
            "b ob",  # spaces not allowed
            "b!",
            "@bob",
            "bob$",
            "b&o&b",
            "bob?",
            "#bob",
            "(bob)",
            "b*ob",
            "%s % bob",
            # Forward slashes
            "user/name",
            "path/to/user",
            # Blocked file extensions
            "username.json",
            "username.csv",
            "username.xls",
            "username.xlsx",
            "username.kml",
            "user.json",
            "user.CSV",
        ]
        users_before = User.objects.count()
        for username in invalid_usernames:
            self._login_user_and_profile({"username": username})
            self.assertEqual(
                User.objects.count(),
                users_before,
                f"Username '{username}' should have been rejected but was accepted",
            )

    def test_allow_valid_usernames(self):
        """Test that various valid username formats are accepted"""
        valid_usernames = [
            # Traditional usernames
            ("testuser1", "user1@example.com"),  # simple username
            ("alice123", "user2@example.com"),  # alphanumeric
            ("john_doe", "user3@example.com"),  # underscore
            ("jane-smith", "user4@example.com"),  # hyphen
            # Email formats
            ("user@example.com", "user5@example.com"),  # email format
            ("user+tag@example.com", "user6@example.com"),  # email with plus
            ("user@mail.example.com", "user7@example.com"),  # subdomain
            # Phone numbers
            ("+1234567890", "user8@example.com"),  # phone number with plus
            ("254123456789", "user9@example.com"),  # phone number
            ("+254-123-456-789", "user10@example.com"),  # phone number with hyphens
            ("254.123.456.789", "user11@example.com"),  # phone number with dots
            # Other valid formats
            ("user.name", "user12@example.com"),  # dot
            ("user.middle.name", "user13@example.com"),  # multiple dots
            ("test.user-name_123", "user14@example.com"),  # mixed characters
            ("username.txt", "user15@example.com"),  # non-blocked extension
        ]
        for username, email in valid_usernames:
            users_before = User.objects.count()
            self._login_user_and_profile({"username": username, "email": email})
            self.assertEqual(
                User.objects.count(),
                users_before + 1,
                f"Valid username '{username}' should have been accepted but was rejected",
            )

    def test_disallow_reserved_name(self):
        users_before = User.objects.count()
        self._login_user_and_profile({"username": "admin"})
        self.assertEqual(User.objects.count(), users_before)

    def test_404_if_user_does_not_exist(self):
        response = self.client.get(reverse(profile, kwargs={"username": "nonuser"}))
        self.assertEqual(response.status_code, 404)

    def test_403_if_unauthorised_user_tries_to_access_api_token_link(self):
        # try accessing with unauthorised user
        factory = RequestFactory()

        # create user alice
        post_data = {
            "username": "alice",
            "email": "alice@columbia.edu",
            "password1": "alicealice102011",
            "password2": "alicealice102011",
            "first_name": "Alice",
            "last_name": "Wonderland",
            "city": "Aliceville",
            "country": "KE",
            "organization": "Alice Inc.",
            "home_page": "alice.com",
            "twitter": "alicemsweet",
        }
        url = "/accounts/register/"
        self.client.post(url, post_data)

        # try accessing api-token with an anonymous user
        request = factory.get("/api-token")
        request.user = AnonymousUser()
        response = api_token(request, "alice")
        self.assertEqual(response.status_code, 302)

        # login with user testuser
        self._login_user_and_profile()

        # try accessing api-token with user 'testuser' but with username 'alice'
        request = factory.get("/api-token")
        request.user = self.user
        response = api_token(request, "alice")
        self.assertEqual(response.status_code, 403)

        # try accessing api-token with user 'testuser' but with username 'testuser'
        request = factory.get("/api-token")
        request.user = self.user
        response = api_token(request, self.user.username)
        self.assertEqual(response.status_code, 200)

    def test_show_single_at_sign_in_twitter_link(self):
        self._login_user_and_profile()
        response = self.client.get(reverse(profile, kwargs={"username": "testuser"}))
        self.assertContains(response, ">@boberama")
        # add the @ sign
        self.user.profile.twitter = "@boberama"
        self.user.profile.save()
        response = self.client.get(reverse(profile, kwargs={"username": "testuser"}))
        self.assertContains(response, ">@boberama")

    def test_url_reverse_with_format_suffix(self):
        """Test that URL reversing works with format suffixes like .json"""

        # Create a simple user
        self._login_user_and_profile({"username": "bob", "email": "bob@example.com"})

        # This should work - reverse URL for user-detail without format
        try:
            url_no_format = reverse("user-detail", kwargs={"username": "bob"})
            self.assertTrue(url_no_format.endswith("/bob"))
        except NoReverseMatch as e:
            self.fail(f"URL reverse without format failed: {e}")

        # This should also work - reverse URL for user-detail with format=json
        try:
            url_with_format = reverse(
                "user-detail", kwargs={"username": "bob", "format": "json"}
            )
            self.assertTrue(url_with_format.endswith("/bob.json"))
        except NoReverseMatch as e:
            self.fail(f"URL reverse with format='json' failed: {e}")
