from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy, gettext as _

from onadata.apps.viewer.models.data_dictionary import DataDictionary


class Command(BaseCommand):
    help = gettext_lazy(
        "This is a one-time command to " "mark start times of old surveys."
    )

    def handle(self, *args, **kwargs):
        for dd in DataDictionary.objects.all():
            try:
                dd.mark_start_time_boolean()
                dd.save()
            except Exception:
                self.stderr.write(
                    _("Could not mark start time for DD: %(data)s") % {"data": repr(dd)}
                )
