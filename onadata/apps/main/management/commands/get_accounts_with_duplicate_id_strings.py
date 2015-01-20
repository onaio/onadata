from django.core.management.base import BaseCommand
from onadata.apps.logger.models.xform import XForm
from django.utils.translation import ugettext_lazy
from django.db.models import Count
from collections import Counter
from pprint import pprint


class Command(BaseCommand):
    help = ugettext_lazy("Retrieves accounts with duplicate id_strings")

    def handle(self, *args, **kwargs):
        duplicates = XForm.objects.values('id_string').annotate(
            id_string_count=Count('id_string')).filter(id_string_count__gt=1)

        duplicates_dict = {}
        if len(duplicates) > 0:
            for a in duplicates:
                xforms = XForm.objects.filter(id_string=a.get('id_string'))
                accounts_with_duplicates = [
                    k for k, v in Counter([a.user for a in xforms]).items()]
                if len(accounts_with_duplicates) > 0:
                    for xform in xforms:
                        if xform.user in accounts_with_duplicates:
                            duplicates_dict[xform.id] = {
                                "no. of submission": xform.num_of_submissions,
                                "username": xform.user.username,
                                "email": xform.user.email
                            }
            self.stdout.write(
                'Forms with duplicate id_strings: %s' % len(duplicates_dict))
            pprint(duplicates_dict)
        else:
            self.stdout.write('Each account has a unique id_string :)')
