#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy

from onadata.apps.main.models import UserProfile
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = ugettext_lazy("Export users and emails")

    def handle(self, *args, **kwargs):
        self.stdout.write(
            '"username","email","first_name","last_name","name","organization"'
        )
        for p in queryset_iterator(UserProfile.objects.all()):
            self.stdout.write(
                u'"{}","{}","{}","{}","{}","{}"'.format(
                    p.user.username, p.user.email, p.user.first_name,
                    p.user.last_name, p.name, p.organization
                )
            )
