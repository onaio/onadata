"""
Delete users management command.
"""
import sys
from django.contrib.auth.models import User
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models import Project
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


def get_user_object_stats(
        username):  # pylint: disable=R0201
    """
    Get User information.
    """
    # Get the number of projects for this user
    user_projects = Project.objects.filter(
        created_by__username=username).count()
    # Get the number of forms
    user_forms = XForm.objects.filter(
        user__username=username).count()
    # Get the number of submissions
    user_sumbissions = Instance.objects.filter(
        user__username=username).count()

    user_response = input(
        "User account '{}' has {} projects, "
        "{} forms and {} submissions. "
        "Do you wish to continue "
        "deleting this account?".format(
            username,
            user_projects,
            user_forms,
            user_sumbissions
            ))

    return user_response


def inactivate_users(users, user_input):
    """
    Soft deletes the user termporarily.
    """
    if users:
        for user in users:
            username, email = user.split(':')
            user_response = 'True'
            if user_input == 'False':
                # If the --user_input flag is not provided.
                # Get acknowledgement from the user on this
                user_response = get_user_object_stats(username)
            if user_response == 'True':
                try:
                    user = User.objects.get(username=username, email=email)
                    # set inactive status on user account
                    user.is_active = False
                    # append a timestamped suffix to the username
                    # to make the initial username available
                    deletion_suffix = timezone.now().strftime('-deleted-at-%s')
                    user.username += deletion_suffix

                    user.save()
                    sys.stdout.write(
                        'User {} deleted successfully.'.format(username))
                    # confirm too that no user exists with provided email
                    if len(User.objects.filter(
                            email=email, is_active=True)) > 1:
                        other_accounts = [
                            user.username for user in User.objects.filter(
                                email=email)]
                        sys.stdout.write(
                            'User accounts {} have the same '
                            'email address with this User'.format(
                                other_accounts))

                except User.DoesNotExist:
                    raise CommandError(
                        'User {} does not exist.'.format(username))
            else:
                sys.stdout.write(
                    'No actions taken')
    else:
        raise CommandError('No User Account provided!')


class Command(BaseCommand):
    """
    Delete users management command.

    :param user_details:
    :param user_input:

    Usage:
    The mandatory arguments are --user_details
    --user_details username1:email username2:email

    The command defaults the values for the --user_input attribute to False
    To change this, pass this in with the value True i.e
    --user_input True
    """
    help = 'Delete users'

    def add_arguments(self, parser):
        parser.add_argument('--user_details', nargs='*')

        parser.add_argument(
            '--user_input',
            help='Confirm deletion of user account',
            default='False'
        )

    def handle(self, *args, **kwargs):
        users = kwargs.get('user_details')
        user_input = kwargs.get('user_input')
        inactivate_users(users, user_input)
