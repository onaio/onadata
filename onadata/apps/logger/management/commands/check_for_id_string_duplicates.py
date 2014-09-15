#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8

from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.model_tools import queryset_iterator
from pprint import pprint


class Command(BaseCommand):
    help = ugettext_lazy("Check for duplicate id_strings")

    def handle(self, *args, **kwargs):
        xforms = XForm.objects.all()
        list1 = [a.id_string for a in xforms]
        list2 = set(map(lambda x: x.lower(), list1))

        if len(list1) == len(list2):
            print "************** NO id_string DUPLICATES FOUND **************"
            continue
        else:
            counter = {}
            for xform in queryset_iterator(xforms):
                id_string = xform.id_string
                xform_id = xform.id
                if id_string not in counter:
                    counter[id_string] = [xform_id]
                else:
                    counter[id_string].append(xform_id)

            duplicate_id_strings = [id_string
                                    for id_string, xform_ids in counter.items()
                                    if len(xform_ids) > 1]

            duplicates_rows = [(xform.id, xform.user, xform.id_string)
                               for xform in queryset_iterator(xforms)
                               if xform.id_string in duplicate_id_strings]

            pprint(duplicates_rows)
