#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8

import glob
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _, gettext_lazy

from onadata.libs.logger.import_tools import import_instances_from_zip
from onadata.libs.logger.models import Instance


IMAGES_DIR = os.path.join(settings.MEDIA_ROOT, "attachments")


class Command(BaseCommand):
    help = gettext_lazy("Import ODK forms and instances.")

    def handle(self, *args, **kwargs):
        if args.__len__() < 2:
            raise CommandError(_("path(xform instances) username"))
        path = args[0]
        username = args[1]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(_("Invalid username %s") % username)
        debug = False
        if debug:
            self.stdout.write(
                _("[Importing XForm Instances from %(path)s]\n") % {"path": path}
            )
            im_count = len(glob.glob(os.path.join(IMAGES_DIR, "*")))
            self.stdout.write(_("Before Parse:"))
            self.stdout.write(_(" --> Images:    %(nb)d") % {"nb": im_count})
            self.stdout.write(
                (_(" --> Instances: %(nb)d") % {"nb": Instance.objects.count()})
            )
        import_instances_from_zip(path, user)
        if debug:
            im_count2 = len(glob.glob(os.path.join(IMAGES_DIR, "*")))
            self.stdout.write(_("After Parse:"))
            self.stdout.write(_(" --> Images:    %(nb)d") % {"nb": im_count2})
            self.stdout.write(
                (_(" --> Instances: %(nb)d") % {"nb": Instance.objects.count()})
            )
