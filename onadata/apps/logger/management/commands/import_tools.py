#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8

import glob
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext as _, ugettext_lazy

from onadata.libs.logger.import_tools import import_instances_from_zip
from onadata.libs.logger.models import Instance


IMAGES_DIR = os.path.join(settings.MEDIA_ROOT, "attachments")


class Command(BaseCommand):
    help = ugettext_lazy("Import ODK forms and instances.")

    def handle(self, *args, **kwargs):
        if args.__len__() < 2:
            raise CommandError(_(u"path(xform instances) username"))
        path = args[0]
        username = args[1]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(_(u"Invalid username %s") % username)
        debug = False
        if debug:
            print (_(u"[Importing XForm Instances from %(path)s]\n")
                   % {'path': path})
            im_count = len(glob.glob(os.path.join(IMAGES_DIR, '*')))
            print _(u"Before Parse:")
            print _(u" --> Images:    %(nb)d") % {'nb': im_count}
            print (_(u" --> Instances: %(nb)d")
                   % {'nb': Instance.objects.count()})
        import_instances_from_zip(path, user)
        if debug:
            im_count2 = len(glob.glob(os.path.join(IMAGES_DIR, '*')))
            print _(u"After Parse:")
            print _(u" --> Images:    %(nb)d") % {'nb': im_count2}
            print (_(u" --> Instances: %(nb)d")
                   % {'nb': Instance.objects.count()})
