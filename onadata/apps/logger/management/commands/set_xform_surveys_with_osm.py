#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8

from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy

from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = ugettext_lazy("Set xform.instances_with_osm")

    def handle(self, *args, **kwargs):
        pks = Attachment.objects.filter(
            extension=Attachment.OSM,
            instance__xform__instances_with_osm=False)\
            .values_list('instance__xform', flat=True).distinct()
        xforms = XForm.objects.filter(pk__in=pks)
        total = xforms.count()
        count = 0

        for xform in queryset_iterator(xforms):
            try:
                xform.instances_with_osm = True
                xform.save()
            except Exception as e:
                self.stderr.write(e)
            else:
                count += 1

        self.stdout.write("%d of %d forms processed." % (count, total))
