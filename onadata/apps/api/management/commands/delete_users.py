from django.contrib.auth.models import User
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models import Project
from onadata.apps.logger.models import Instance
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Delete users'

    def add_arguments(self, parser):
        parser.add_argument('user', nargs='*')

    def handle(self, *args, **kwargs):
        users = kwargs['user']
        if users:
            positive_reponses = ["Yes", "yes", "y", "Y"]
            negative_reponses = ["No", "no", "n", "N"]
            for user in users:
                user_details = user.split(':')
                username = user_details[0]
                user_projects = self.get_user_projects(username)
                user_forms = len(self.get_user_forms(username))

                user_input = input("User has {} projects, {} forms. \
                        Do you wish to continue deleting this account?".format(
                        user_projects, user_forms))

            if user_input in positive_reponses:
                try:
                    self.delete_user(username)
                except User.DoesNotExist:
                    self.stdout.write('User %s does not exist.' % username)

            elif user_input in negative_reponses:
                pass
            else:
                input('Enter space-delimited list of users: ')

        else:
            input('Enter space-delimited list of users: ').split(',')

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

    def delete_user(self, username):
        try:
            user = User.objects.get(username=username)
            user.delete()
            self.stdout.write(
                'User %s deleted with success!' % (username))
        except User.DoesNotExist:
            self.stdout.write('User %sdoes not exist.' % username)
