# -*- coding: utf-8 -*-
"""Test create user profile management command."""
from django.contrib.auth.models import User
from onadata.apps.main.models.user_profile import UserProfile
from django.core.management import call_command
from django.utils.six import StringIO
from onadata.apps.main.tests.test_base import TestBase


class CreateUserProfilesTest(TestBase):
    """Test create user profile management command."""

    def test_create_user_profiles(self):
        """
        Test that create_user_profiles management command
        successfully creates a user profile for users
        missing profiles.
        """
        user = User.objects.create(
            username='dave', email='dave@example.com')
        with self.assertRaises(UserProfile.DoesNotExist):
            _ = user.profile
        out = StringIO()
        call_command(
            'create_user_profiles',
            stdout=out
        )
        user.refresh_from_db()
        # Assert profile is retrievable;
        profile = user.profile
        self.assertEqual(profile.user, user)
        self.assertEqual(
            'User Profiles successfully created.\n',
            out.getvalue())
