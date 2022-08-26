#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8
"""
export_user_emails command - prints a CSV of usernames and emails.
"""
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy

from onadata.apps.main.models import UserProfile
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    """Export users and emails"""

    help = gettext_lazy("Export users and emails")

    def handle(self, *args, **kwargs):
        self.stdout.write(
            '"username","email","first_name","last_name","name","organization"'
        )
        for profile in queryset_iterator(UserProfile.objects.all()):
            self.stdout.write(
                f'"{profile.user.username}","{profile.user.email}",'
                f'"{profile.user.first_name}","{profile.user.last_name}",'
                f'"{profile.name}","{profile.organization}"'
            )
