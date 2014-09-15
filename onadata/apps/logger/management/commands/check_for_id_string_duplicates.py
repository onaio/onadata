#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = ugettext_lazy("Check for duplicate id_strings in XForms per user")

    def handle(self, *args, **kwargs):
        for user in User.objects.all():
            xforms = XForm.objects.filter(user=user)
            dict1 = {a.id: a.id_string for a in xforms}
            list1 = set(map(lambda x: x.lower(), dict1.values()))

            if len(list1) == len(dict1.values()):
                continue
            else:
                print ">>>>>>>>>>>>>>>>>> DUPLICATES EXIST"
                flipped = {}
                for key, value in dict1.items():
                    if value not in flipped:
                        flipped[value] = [key]
                    else:
                        flipped[value].append(key)

                for duplicate_id_string, ids in flipped.items():
                    if len(ids) > 1:
                        from_second = ids[1:]
                        for xform_id in from_second:
                            for xform in queryset_iterator(xforms):
                                try:
                                    if xform.id == xform_id:
                                        xform.id_string = "%s_%s" % (
                                            duplicate_id_string,
                                            from_second.index(xform_id) + 1)
                                        xform.save()
                                except Exception as e:
                                    print e
