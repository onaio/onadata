"""
Test delete user management command.
"""
import sys
from unittest import mock
from django.utils.six import StringIO
from django.contrib.auth.models import User
from django.core.management import call_command
from onadata.apps.main.tests.test_base import TestBase


class DeleteUserTest(TestBase):
    """
    Test delete user management command.
    """
    def test_delete_users_with_input(self):
        """
        Test that a user account is deleted automatically
        when the user_input field is provided as true
        """
        user = User.objects.create(
            username="bruce",
            email="bruce@gmail.com")
        username = user.username
        email = user.email
        out = StringIO()
        sys.stdout = out
        new_user_details = [username+':'+email]
        call_command(
            'delete_users',
            user_details=new_user_details,
            user_input=True,
            stdout=out)

        self.assertEqual(
            "User bruce deleted successfully.",
            out.getvalue())

    @mock.patch(
        "onadata.apps.api.management.commands.delete_users.input")
    def test_delete_users_no_input(self, mock_input):
        """
        Test that when user_input is not provided,
        the user account stats are provided for that user account
        before deletion
        """
        def side_effect(str):
            return False
        mock_input.side_effect = side_effect
        user = User.objects.create(
            username="barbie",
            email="barbie@gmail.com")
        username = user.username
        email = user.email
        out = StringIO()
        sys.stdout = out
        new_user_details = [username+':'+email]
        call_command(
            'delete_users',
            user_details=new_user_details,
            stdout=out)

        self.assertEqual(
            "User account 'barbie' has 0 projects, "
            "0 forms and 0 submissions. "
            "Do you wish to continue deleting this account?",
            out.getvalue())
