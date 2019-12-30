from six import StringIO

from django.core.management import call_command
from onadata.apps.main.tests.test_base import TestBase


class DeleteUserTest(TestBase):
    def test_delete_users(self):
        self._publish_transportation_form_and_submit_instance()
        username = self.xform.user.username
        self.xform.user.email = 'bob@gmail.com'
        email = self.xform.user.email

        # delete user account when user_input is True
        user_details = username+':'+email
        out = StringIO()
        call_command(
                'delete_users', user_details, user_input=True, stdout=out)
        self.assertIn(
            'User bob deleted with success!', out.getvalue())

        # when user_input is False user accounts will not be deleted
        user_deno = self._create_user('deno', 'deno')
        username = user_deno.username
        self.xform.user.email = 'deno@gmail.com'
        email = self.xform.user.email

        new_user_details = username+':'+email
        call_command(
                'delete_users', new_user_details, user_input=False, stdout=out)
        self.assertIn(
            'User account deno not deleted.', out.getvalue())
