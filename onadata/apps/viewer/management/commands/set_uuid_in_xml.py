# -*- coding: utf-8 -*-
"""
set_uuid_in_xml command - Insert UUID into XML of all existing XForms.
"""
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _, gettext_lazy

from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    """
    set_uuid_in_xml command - Insert UUID into XML of all existing XForms.
    """

    help = gettext_lazy("Insert UUID into XML of all existing XForms")

    def handle(self, *args, **kwargs):
        self.stdout.write(
            _("%(nb)d XForms to update") % {"nb": DataDictionary.objects.count()}
        )
        for i, xform in enumerate(queryset_iterator(DataDictionary.objects.all())):
            if xform.xls:
                xform.set_uuid_in_xml()
                # pylint: disable=bad-super-call
                super(DataDictionary, xform).save()
            if (i + 1) % 10 == 0:
                self.stdout.write(_(f"Updated {i} XForms..."))
