from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _, gettext_lazy

from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = gettext_lazy("Insert UUID into XML of all existing XForms")

    def handle(self, *args, **kwargs):
        self.stdout.write(_('%(nb)d XForms to update')
                          % {'nb': DataDictionary.objects.count()})
        for i, dd in enumerate(
                queryset_iterator(DataDictionary.objects.all())):
            if dd.xls:
                dd.set_uuid_in_xml()
                super(DataDictionary, dd).save()
            if (i + 1) % 10 == 0:
                self.stdout.write(_('Updated %(nb)d XForms...') % {'nb': i})
