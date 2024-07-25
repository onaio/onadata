#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8
"""
Set xform.instances_with_osm
"""
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy

from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    """Set xform.instances_with_osm"""

    help = gettext_lazy("Set xform.instances_with_osm")

    def handle(self, *args, **kwargs):
        pks = (
            Attachment.objects.filter(
                extension=Attachment.OSM, instance__xform__instances_with_osm=False
            )
            .values_list("instance__xform", flat=True)
            .distinct()
        )
        xforms = XForm.objects.filter(pk__in=pks)
        total = xforms.count()
        count = 0

        for xform in queryset_iterator(xforms):
            try:
                xform.instances_with_osm = True
                xform.save()
            # pylint: disable=broad-except
            except Exception as error:
                self.stderr.write(error)
            else:
                count += 1

        self.stdout.write(f"{count} of {total} forms processed.")
