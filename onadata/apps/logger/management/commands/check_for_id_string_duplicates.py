#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8

from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy
from onadata.apps.logger.models.xform import XForm
from pprint import pprint


class Command(BaseCommand):
    help = ugettext_lazy("Check for duplicate id_strings")

    def handle(self, *args, **kwargs):
        xforms = XForm.objects.all()
        list1 = [xform.id_string for xform in xforms]
        list2 = set(map(lambda x: x.lower(), list1))

        if len(list1) != len(list2):
            counter = {}
            xform_list = [(xform.id, xform.id_string) for xform in xforms]
            for xform_id, xform_id_string in xform_list:
                counter.setdefault(xform_id_string, []).append(xform_id)

            duplicate_id_strings = [id_string
                                    for id_string, xform_ids in counter.items()
                                    if len(xform_ids) > 1]

            duplicates_rows = [(xform.id, xform.user, xform.id_string)
                               for xform in xforms
                               if xform.id_string in duplicate_id_strings]

            pprint(duplicates_rows)
