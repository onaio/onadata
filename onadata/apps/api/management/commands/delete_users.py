from django.contrib.auth.models import User
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models import Project
from onadata.apps.logger.models import Instance
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Delete users'

    def add_arguments(self, parser):
        parser.add_argument('user', nargs='*')

        parser.add_argument(
                '--user_input',
                action='store_true',
                help='Confirm deletion of user account',
            )

    def handle(self, *args, **kwargs):
        users = kwargs['user']
        user_input = kwargs['user_input']

        if users and user_input is not None:
            for user in users:
                user_details = user.split(':')
                username = user_details[0]
                user_projects = self.get_user_projects(username)
                user_forms = self.get_user_forms(username)
                if user_input is True:
                    return self.get_user_account_details(username)
                elif user_input is False:
                    return self.stdout.write(
                        'User account {} not deleted.'.format(username))

        user_projects = self.get_user_projects(username)
        user_forms = len(self.get_user_forms(username))
        user_input = input("User has {} projects, {} forms. \
            Do you wish to continue deleting this account?".format(
            user_projects, user_forms))

        if user_input is True:
            self.get_user_account_details(username)
        else:
            self.stdout.write('User account {} not deleted.'.format(username))

    def get_user_projects(self, username):  # pylint: disable=R0201
        user = User.objects.get(username=username)
        user_projects = Project.objects.filter(created_by=user).count()

        return user_projects

    def get_user_forms(self, username):  # pylint: disable=R0201
        user = User.objects.get(username=username)
        user_forms = XForm.objects.filter(user=user)

        for form in user_forms:
            form_name = form.title
            form_sumbissions = Instance.objects.filter(xform=form).count()

            result = {
                form_name: form_sumbissions,
            }

            return result

        return len(user_forms)

    def get_user_account_details(self, username):  # pylint: disable=R0201
        try:
            self.delete_user(username)
            self.stdout.write(
                'User {} deleted with success!'.format(username))
        except User.DoesNotExist:
            self.stdout.write('User {} does not exist.' % username)

    def delete_user(self, username):
        try:
            user = User.objects.get(username=username)
            user.delete()
        except User.DoesNotExist:
            self.stdout.write('User {} does not exist.' % username)
