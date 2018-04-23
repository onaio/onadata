#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
from __future__ import absolute_import

import glob
import os

from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy

from onadata.apps.logger.models import XForm


class Command(BaseCommand):
    help = ugettext_lazy("Import a folder of XForms for ODK.")

    def handle(self, *args, **kwargs):
        path = args[0]
        for form in glob.glob(os.path.join(path, "*")):
            f = open(form)
            XForm.objects.get_or_create(xml=f.read(), active=False)
            f.close()
