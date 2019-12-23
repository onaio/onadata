from django.contrib.auth.models import User
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models import Project
from onadata.apps.logger.models import Instance
from django.db.utils import IntegrityError
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Delete users'

    def add_arguments(self, parser):
        parser.add_argument('user', nargs='*')

    def handle(self, *args, **kwargs):
        users = kwargs['user']
        if users:
            usernames = []
            for user in users:
                user_details = user.split(':')
                import ipdb; ipdb.set_trace()
                username = user_details[0]
                email = user_details[1]
                user_projects = self.get_user_projects(username)
                user_forms = self.get_user_forms(username)
                user_input = input("User has {} projects, {} forms with {} submissions. \
                    Do you wish to continue deleting this account?".format(user_projects, user_forms, user_forms))

            positive_reponses = ["Yes","yes","y","Y"]
            negative_reponses = ["No","no","n","N"]

            if user_input in positive_reponses:
                import ipdb; ipdb.set_trace()
                usernames.append(username)
            elif user_input in negative_reponses:
                pass
            else:
                input('Enter space-delimited list of users: ')

            self.delete_user(usernames)
        else:
            raw_input('Enter space-delimited list of users: ').split(',')
            
            
        

    def get_user_projects(self, username):
        user = User.objects.get(username=username)

        user_projects = Project.objects.filter(created_by=user).count()

        return user_projects

    def get_user_forms(self, username):
        user = User.objects.get(username=username)

        user_forms = XForm.objects.filter(user=user).count()
        forms = XForm.objects.filter(user=user)

        for form in forms:
            form_name = form.name
            form_sumbissions = Instance.objects.filter(xform=form_name).count()

        return user_forms

    def delete_user(self, usernames):
        import ipdb; ipdb.set_trace()
        for username in usernames:
            try:
                user = User.objects.get(username=username)
                user.delete()
                self.stdout.write(
                    'User %s deleted with success!' % (username))
            except User.DoesNotExist:
                self.stdout.write('User %sdoes not exist.' % username)