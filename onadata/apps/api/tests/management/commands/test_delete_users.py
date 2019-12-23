from io import StringIO
from django.core.management import call_command
from django.contrib.auth.models import User
from onadata.apps.main.tests.test_base import TestBase


class DeleteUserTest(TestBase):
    def test_delete_users(self):
        out = StringIO()
        user1, created = User.objects.get_or_create(username='scott')
        user1.email = 'scott@gmail.com'
        user1.save()
        user2, created = User.objects.get_or_create(username='scotty')
        user2.email = 'scotty@gmail.com'
        user2.save()

        users = [user1, user2]

        for user in users:
            username = user.username
            email = user.email
            user_details = username+':'+email
        
            call_command('delete_users', user_details, stdout=out)
            self.assertIn('User scott deleted with success!', out.getvalue())
        
        


