from django.contrib.auth.models import User
from onadata.apps.main.models.user_profile import UserProfile
from django.core.management import call_command
from django.utils.six import StringIO

from onadata.apps.main.tests.test_base import TestBase


class CreateUserProfilesTest(TestBase):
    def test_create_user_profiles(self):
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
        try:
            _ = user.profile
        except UserProfile.DoesNotExist:
            assert False
        self.assertEqual(
            'User Profiles successfully created.\n',
            out.getvalue())
