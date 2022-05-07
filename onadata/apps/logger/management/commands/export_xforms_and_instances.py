#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
# -*- coding=utf-8 -*-
"""
export_xformx_and_instances - exports XForms and submission instances into JSON files.
"""
import os

from django.core.management.base import BaseCommand
from django.core.serializers import serialize
from django.utils.translation import gettext_lazy
from django.conf import settings
from onadata.apps.logger.models import XForm, Instance

PROJECT_ROOT = settings.PROJECT_ROOT


class Command(BaseCommand):
    """Export ODK forms and instances to JSON."""

    help = gettext_lazy("Export ODK forms and instances to JSON.")

    def handle(self, *args, **kwargs):
        """Export ODK forms and instances to JSON."""
        fixtures_dir = os.path.join(PROJECT_ROOT, "json_xform_fixtures")
        if not os.path.exists(fixtures_dir):
            os.mkdir(fixtures_dir)

        xform_fp = os.path.join(fixtures_dir, "a-xforms.json")
        instance_fp = os.path.join(fixtures_dir, "b-instances.json")

        with open(xform_fp, "w", encoding="utf-8") as xfp:
            xfp.write(serialize("json", XForm.objects.all()))
            xfp.close()

        with open(instance_fp, "w", encoding="utf-8") as ifp:
            ifp.write(serialize("json", Instance.objects.all()))
            ifp.close()
