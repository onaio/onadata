from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from onadata.apps.logger.models import Project


class Command(BaseCommand):
    help = 'A command to reassign a project form one user to the other.'

    errors = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--currentowner',
            help='Username of the current owner of of the projects',
        )
        parser.add_argument(
            '--newowner',
            help='TUsername of new owner of the projects',
        )

    def get_user(self, username):
        um = get_user_model()
        user = None
        try:
            user = um.objects.get(username=username)
        except um.DoesNotExist:
            self.errors.append("User {} does not exist \n".format(username))
        return user

    def handle(self, *test_labels, **options):
        from_user = self.get_user(options['currentowner'])
        to_user = self.get_user(options['newowner'])
        if self.errors:
            self.stdout.write(self.style.ERROR(''.join(self.errors)))
            return

        projects = Project.objects.filter(organization=from_user)
        for project in projects:
            project.organization = to_user
            project.created_by = to_user
            project.save()
        assert Project.objects.filter(organization=from_user).count() == 0
        self.stdout.write(
            self.style.SUCCESS('Projects reassigned successfully')
        )
