"""Allow deletion of a user via the command line. """

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from onadata.apps.logger.models import XForm, Project


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--user_email',
            action='store_false',
            dest='user_email',
            help='Email of the user that you want to delete',
        )
        parser.add_argument(
            '--username',
            action='store_false',
            dest='username',
            help='Username of the user that you want to delete',
        )
        parser.add_argument(
            '--form_name',
            action='store_false',
            dest='form_name',
            help='A form that belongs to the user that you want to delete',
        )
        parser.add_argument(
            '--project_name',
            action='store_false',
            dest='project_name',
            help='A project that belong to the user that you want to delete',
        )

    def handle(self, *args, **options):
        """
        Delete all the objects that belong to the user. The XForm, the Project
        """
        user = User.objects.get(
            email=options['user_email'], username=options['username'])

        try:
            XForm.objects.get(user=user, name=options['form_name'])
        except XForm.DoesNotExist:
            raise CommandError("The project provided does not exist")

        try:
            Project.objects.get(user=user, name=options['project_name'])
        except:
            raise CommandError("The project provided does not exist")

        XForm.objects.filter(user=user).delete()
        Project.objects.filter(user=user).delete()
        User.objects.delete()
        self.stdout.write(
            self.style.SUCCESS('User {} deleted successfully'.format(
                options['user_email']))
        )
