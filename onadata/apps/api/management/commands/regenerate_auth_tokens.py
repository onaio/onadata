from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils.translation import gettext as _
from optparse import make_option
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = _(u"Regenerate Authentication Tokens")
    option_list = BaseCommand.option_list + (
        make_option('--users', '-u',
                    action='store_true',
                    dest='users',
                    default=False,
                    help='Users to Regenerate Tokens'),
        )

    def handle(self, *args, **options):
        ALL = "all"
        # check if the users option has been used and
        # at least one argument passed
        if options['users'] and len(args) > 0:
            # check if keyword 'all' has been included in the list of arguments
            if len(args) > 1 and ALL in args:
                self.stdout.write("Keyword 'all' should be passed as single "
                                  "argument and not be part of a list")
            else:
                # check if the single argument passed in 'all'
                if len(args) == 1 and args[0] == ALL:
                    Token.objects.all().delete()
                    for user in User.objects.all():
                        Token.objects.create(user=user)
                    self.stdout.write("All users' api tokens have "
                                      "been updated")
                else:
                    users = User.objects.filter(username__in=args)
                    usernames = [a.username for a in users]
                    # check if ALL usernames provide were valid
                    if len(users) == 0:
                        self.stdout.write("The usernames provided were "
                                          "invalid")
                    else:
                        # check some of the usernames passed were invalid
                        if len(users) != len(args):
                            users_not_found = list(set(args) - set(usernames))
                            self.stdout.write("The following usersames don't "
                                              "exist: %s" % users_not_found)

                        for user in users:
                            Token.objects.get(user=user).delete()
                            Token.objects.create(user=user)
                        self.stdout.write("The API tokens for the users "
                                          "provided have been updated")

        else:
            print "This command takes at least one argument with the " \
                  "'--users' or '-u' option e.g -u <username>"
