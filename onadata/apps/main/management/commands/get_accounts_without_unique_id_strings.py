from django.core.management.base import BaseCommand
from onadata.apps.logger.models.xform import XForm
from django.utils.translation import ugettext_lazy
from django.db.models import Count
from pprint import pprint


class Command(BaseCommand):
    help = ugettext_lazy("Retrieves accounts with non-unique id_strings")

    def handle(self, *args, **kwargs):
        duplicate_id_string = XForm.objects.values('id_string').annotate(
            id_string_count=Count('id_string'),
            username_count=Count('user__username')
        ).values(
            'pk', 'user__username', 'user__email', 'id_string',
            'num_of_submissions'
        ).filter(id_string_count__gt=1, username_count__gt=1)

        if len(duplicate_id_string) > 0:
            self.stdout.write(
                "The following are the duplicates...")
            pprint(duplicate_id_string)
        else:
            self.stdout.write("There are no id_string duplicates in accounts")
