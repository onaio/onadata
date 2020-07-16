from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _

from onadata.apps.api.models.odk_token import ODKToken


def increase_odk_token_lifetime(days: int, username: str):
    qs = ODKToken.objects.filter(
            user__username=username, status=ODKToken.ACTIVE)
    if qs.count() < 1:
        return False

    token = qs.first()
    updated_expiry_date = token.expires + timedelta(days=days)
    token.expires = updated_expiry_date.astimezone(token.expires.tzinfo)
    token.save()
    return True


class Command(BaseCommand):
    help = _("Increase ODK Token lifetime for a particular user.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            '-d',
            default=30,
            dest='days',
            help='Number of days to increase the token lifetime by.')
        parser.add_argument(
            '--username',
            '-u',
            dest='username',
            help='The users username'
        )

    def handle(self, *args, **options):
        username = options.get('username')
        days = options.get('days')

        if not username:
            raise CommandError('No username provided.')

        created = increase_odk_token_lifetime(days, username)
        if not created:
            raise CommandError(f'User {username} has no active ODK Token.')
        self.stdout.write(
            f'Increased the lifetime of ODK Token for user {username}')
