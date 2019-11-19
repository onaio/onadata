from io import StringIO
from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import TestCase


class DeleteUserTest(TestCase):
    def test_delete_users(self):
        out = StringIO()
        user, created = User.objects.get_or_create(username='scott')
        user.email = 'scott@gmail.com'
        username = user.username
        email = user.email
        user_details = username+' - '+email
        call_command('delete_users', user_details, stdout=out)
        self.assertIn('User scott does not exist.', out.getvalue())
