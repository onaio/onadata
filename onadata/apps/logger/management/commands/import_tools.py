#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
# -*- coding: utf-8 -*-
"""
import_tools - import ODK formms and instances.
"""
import glob
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from onadata.apps.logger.import_tools import import_instances_from_zip
from onadata.apps.logger.models import Instance

IMAGES_DIR = os.path.join(settings.MEDIA_ROOT, "attachments")


class Command(BaseCommand):
    """Import ODK forms and instances."""

    help = gettext_lazy("Import ODK forms and instances.")

    def handle(self, *args, **kwargs):
        """Import ODK forms and instances."""
        if len(args) < 2:
            raise CommandError(_("path(xform instances) username"))
        path = args[0]
        username = args[1]
        try:
            user = get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist as error:
            raise CommandError(_(f"Invalid username {username}")) from error
        debug = False
        if debug:
            self.stdout.write(_(f"[Importing XForm Instances from {path}]\n"))
            im_count = len(glob.glob(os.path.join(IMAGES_DIR, "*")))
            self.stdout.write(_("Before Parse:"))
            self.stdout.write(_(f" --> Images:    {im_count}"))
            self.stdout.write((_(f" --> Instances: {Instance.objects.count()}")))
        import_instances_from_zip(path, user)
        if debug:
            im_count2 = len(glob.glob(os.path.join(IMAGES_DIR, "*")))
            self.stdout.write(_("After Parse:"))
            self.stdout.write(_(f" --> Images:    {im_count2}"))
            self.stdout.write((_(f" --> Instances: {Instance.objects.count()}")))
