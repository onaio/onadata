#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4
"""
import_forms - loads XForms from a given path.
"""
from __future__ import absolute_import

import glob
import os

from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy

from onadata.apps.logger.models import XForm


class Command(BaseCommand):
    """Import a folder of XForms for ODK."""

    help = gettext_lazy("Import a folder of XForms for ODK.")

    # pylint: disable=unused-argument
    def handle(self, *args, **kwargs):
        """Import a folder of XForms for ODK."""
        path = args[0]
        for form in glob.glob(os.path.join(path, "*")):
            with open(form, encoding="utf-8") as xform_xml_file:
                XForm.objects.get_or_create(
                    xml=xform_xml_file.read(), downloadable=False
                )
