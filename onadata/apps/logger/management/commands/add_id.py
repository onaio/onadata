from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy
from django.core.management.base import BaseCommand
from django.conf import settings

from onadata.apps.logger.models import Instance, XForm
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    args = '<username>'
    help = ugettext_lazy("Sync account with '_id'")

    def handle(self, *args, **kwargs):

        # username
        if args:
            users = User.objects.filter(username__contains=args[0])
        else:
            # All the accounts
            self.stdout.write("Fetching all the account {}", ending='\n')
            users = queryset_iterator(
                User.objects.exclude(pk=settings.ANONYMOUS_USER_ID))

        for user in users:
            self.add_id(user)

    def add_id(self, user):
        self.stdout.write("Syncing for account {}".format(user.username),
                          ending='\n')
        xforms = XForm.objects.filter(user=user)

        count = 0
        failed = 0
        for instance in Instance.objects.filter(
                xform__downloadable=True, xform__in=xforms)\
                .extra(where=['("logger_instance".json->>%s) is null'],
                       params=["_id"]).iterator():
            try:
                instance.save()
                count += 1
            except Exception as e:
                failed += 1
                self.stdout.write(str(e), ending='\n')
                pass

        self.stdout.write("Syncing for account {}. Done. Success {}, Fail {}"
                          .format(user.username, count, failed),
                          ending='\n')
