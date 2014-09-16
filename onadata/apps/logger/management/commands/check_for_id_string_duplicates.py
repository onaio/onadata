#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8

from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy
from onadata.apps.logger.models.xform import XForm
from django.contrib.auth.models import User
from onadata.libs.utils.model_tools import queryset_iterator
from pprint import pprint


class Command(BaseCommand):
    help = ugettext_lazy("Check for duplicate id_strings")

    def handle(self, *args, **kwargs):
        for user in queryset_iterator(User.objects.all()):
            xforms = XForm.objects.filter(user=user)
            list1 = [xform.id_string for xform in queryset_iterator(xforms)]
            list2 = set(map(lambda x: x.lower(), list1))

            if len(list1) != len(list2):
                counter = {}
                xform_list = [(xform.id, xform.id_string)
                              for xform in queryset_iterator(xforms)]
                for xform_id, xform_id_string in xform_list:
                    counter.setdefault(xform_id_string, []).append(xform_id)

                dupl_id_strings = [id_string
                                   for id_string, xform_ids in counter.items()
                                   if len(xform_ids) > 1]

                duplicates_rows = [(xform.id, xform.user, xform.id_string)
                                   for xform in queryset_iterator(xforms)
                                   if xform.id_string in dupl_id_strings]

                pprint(duplicates_rows)
