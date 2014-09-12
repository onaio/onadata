#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8

from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy

from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = ugettext_lazy("Change id strings in xforms to lower cases")

    def handle(self, *args, **kwargs):
        xforms = XForm.objects.all()
        for xform in queryset_iterator(xforms):
            try:
                xform.id_string = xform.id_string.lower()
                xform.save()
            except Exception as e:
                print e
        print "xform id strings have been converted to lower case"
