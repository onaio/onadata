from six import StringIO

from django.core.management import call_command
from onadata.apps.main.tests.test_base import TestBase


class DeleteUserTest(TestBase):
    def test_delete_users(self):
        self._publish_transportation_form_and_submit_instance()
        username = self.xform.user.username
        self.xform.user.email = 'bob@gmail.com'
        email = self.xform.user.email

        user_details = username+':'+email
        out = StringIO()
        call_command(
                'delete_users', user_details, stdout=out)
        self.assertIn(
            'User bob deleted with success!', out.getvalue())
