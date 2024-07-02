# -*- coding: utf-8 -*-
"""
Sync account with '_id'
"""
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy
from django.core.management.base import BaseCommand
from django.conf import settings

from onadata.apps.logger.models import Instance, XForm
from onadata.libs.utils.model_tools import queryset_iterator


User = get_user_model()


class Command(BaseCommand):
    """Sync account with '_id'"""

    args = "<username>"
    help = gettext_lazy("Sync account with '_id'")

    def handle(self, *args, **kwargs):

        # username
        if args:
            users = User.objects.filter(username__contains=args[0])
        else:
            # All the accounts
            self.stdout.write("Fetching all the accounts.", ending="\n")
            users = User.objects.exclude(
                username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
            )

        for user in queryset_iterator(users):
            self.add_id(user)

    def add_id(self, user):
        """Append _id in submissions for the specifing ``user``."""
        self.stdout.write(f"Syncing for account {user.username}", ending="\n")
        xforms = XForm.objects.filter(user=user)

        count = 0
        failed = 0
        for instance in (
            Instance.objects.filter(xform__downloadable=True, xform__in=xforms)
            .extra(where=['("logger_instance".json->>%s) is null'], params=["_id"])
            .iterator()
        ):
            try:
                instance.save()
                count += 1
            # pylint: disable=broad-except
            except Exception as error:
                failed += 1
                self.stdout.write(str(error), ending="\n")

        self.stdout.write(
            f"Syncing for account {user.username}. Done. "
            f"Success {count}, Fail {failed}",
            ending="\n",
        )
