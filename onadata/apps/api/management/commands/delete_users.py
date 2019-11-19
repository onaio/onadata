from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Delete users'

    def add_arguments(self, parser):
        parser.add_argument('user', nargs='*')

    def handle(self, *args, **kwargs):
        users = kwargs['user']

        if users:
            for user in users:
                user_details = user.split('-')
                username = user_details[0]
                email = user_details[1]
                try:
                    user = User.objects.get(username=username)
                    user.delete()
                    self.stdout.write(
                        'User %s deleted with success!' % (username))
                    try:
                        user = User.objects.get(email=email)
                        user.delete()
                        self.stdout.write(
                            'User %s deleted with success!' % (email))
                    except User.DoesNotExist:
                        self.stdout.write('User %s does not exist.' % email)
                except User.DoesNotExist:
                    self.stdout.write('User %sdoes not exist.' % username)
