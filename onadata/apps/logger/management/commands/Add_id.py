from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy
from django.core.management.base import BaseCommand
from django.conf import settings

from onadata.apps.logger.models import Instance, XForm
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = ugettext_lazy("Sync account with '_id'")

    def handle(self, *args, **kwargs):

        username = args[0]
        if username:
            users = User.objects.filter(username__contains=username)

            for user in users:
                self.add_id(user)
        else:
            # Get all the users
            for user in queryset_iterator(
                    User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)):
                self.add_id(user)

    def add_id(self, user):
        self.stdout.write("Syncing for account {}".format(user.username),
                          ending='\n')
        xforms = XForm.objects.filter(user=user)

        count = 0
        failed = 0
        for i in Instance.objects.filter(xform__downloadable=True,
                                         xform__in=xforms)\
                .extra(where=['("logger_instance".json->>%s) is null'],
                       params=["_id"]).iterator():
            try:
                i.save()
                count += 1
            except Exception as e:
                failed += 1
                self.stdout.write(str(e), ending='\n')
                pass

        self.stdout.write("Syncing for account {}. Done. Success {}, Fail {}"
                          .format(user.username, count, failed),
                          ending='\n')
