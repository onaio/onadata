"""
Test delete user management command.
"""
import sys
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command

from six import StringIO

from onadata.apps.api.management.commands.delete_users import get_user_object_stats
from onadata.apps.main.tests.test_base import TestBase

User = get_user_model()


class DeleteUserTest(TestBase):
    """
    Test delete user management command.
    """

    def test_delete_users_with_input(self):
        """
        Test that a user account is deleted automatically
        when the user_input field is provided as true
        """
        user = User.objects.create(username="bruce", email="bruce@gmail.com")
        username = user.username
        email = user.email
        out = StringIO()
        sys.stdout = out
        new_user_details = [username + ":" + email]
        call_command(
            "delete_users", user_details=new_user_details, user_input="True", stdout=out
        )

        self.assertEqual("User bruce deleted successfully.", out.getvalue())

        with self.assertRaises(User.DoesNotExist):
            User.objects.get(email="bruce@gmail.com")

    @patch("onadata.apps.api.management.commands.delete_users.input")
    def test_delete_users_no_input(self, mock_input):  # pylint: disable=R0201
        """
        Test that when user_input is not provided,
        the user account stats are provided for that user account
        before deletion
        """
        user = User.objects.create(username="barbie", email="barbie@gmail.com")
        username = user.username
        get_user_object_stats(username)

        mock_input.assert_called_with(
            "User account 'barbie' has 0 projects, "
            "0 forms and 0 submissions. "
            "Do you wish to continue deleting this account?"
        )
