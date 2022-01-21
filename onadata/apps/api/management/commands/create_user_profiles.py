# -*- coding: utf-8 -*-
"""
Management Command to add missing user profiles to users
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils.translation import gettext as _

from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = _("Build out missing user profiles")

    def handle(self, *args, **options):
        # get all users
        try:
            users = User.objects.all()
            for user in queryset_iterator(users):
                try:
                    profile = user.profile
                except UserProfile.DoesNotExist:
                    profile, _ = UserProfile.objects.get_or_create(user=user)
                    profile.save()
        except User.DoesNotExist:
            pass

        self.stdout.write("User Profiles successfully created.")
