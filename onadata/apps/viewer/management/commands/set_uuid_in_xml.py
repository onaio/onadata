from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _, ugettext_lazy

from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = ugettext_lazy("Insert UUID into XML of all existing XForms")

    def handle(self, *args, **kwargs):
        print (_('%(nb)d XForms to update')
               % {'nb': DataDictionary.objects.count()})
        for i, dd in enumerate(
                queryset_iterator(DataDictionary.objects.all())):
            if dd.xls:
                dd._set_uuid_in_xml()
                super(DataDictionary, dd).save()
            if (i + 1) % 10 == 0:
                print _('Updated %(nb)d XForms...') % {'nb': i}
