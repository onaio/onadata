#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8
"""
Import a folder of XForms for ODK.
"""
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy

from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    """Import a folder of XForms for ODK."""

    help = gettext_lazy("Import a folder of XForms for ODK.")

    def handle(self, *args, **kwargs):
        xforms = XForm.objects.all()
        total = xforms.count()
        count = 0
        for xform in queryset_iterator(XForm.objects.all()):
            has_geo = xform.geocoded_submission_count() > 0
            try:
                xform.instances_with_geopoints = has_geo
                xform.save()
            # pylint: disable=broad-except
            except Exception as error:
                self.stderr.write(error)
            else:
                count += 1
        self.stdout.write(f"{count} of {total} forms processed.")
