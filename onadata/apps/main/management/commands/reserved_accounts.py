from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy
from onadata.apps.main.forms import RegistrationFormUserProfile


class Command(BaseCommand):
    help = ugettext_lazy("Reserved user accounts ")

    option_list = BaseCommand.option_list

    def handle(self, *args, **kwargs):

       f = open('reserved_accounts.txt', 'wb')
       for i in RegistrationFormUserProfile._reserved_usernames: f.write("%s\n" % i)
       f.close()
