from django.core.management.base import BaseCommand
from onadata.apps.logger.models.xform import XForm
from django.utils.translation import ugettext_lazy
from django.db.models import Count
from pprint import pprint


class Command(BaseCommand):
    help = ugettext_lazy("Retrieves accounts with duplicate id_strings")

    def handle(self, *args, **kwargs):
        duplicates = XForm.objects.values(
            'id_string', 'user__username').annotate(
            id_string_count=Count('id_string')).filter(id_string_count__gt=1)
        duplicates_dict = {}
        if len(duplicates) > 0:
            for a in duplicates:
                xforms = XForm.objects.filter(
                    id_string=a.get('id_string'),
                    user__username=a.get('user__username'))
                for xform in xforms:
                    if duplicates_dict.get(xform.user) is None:
                        duplicates_dict[xform.user] = [{
                            "form id": xform.pk,
                            "no. of submission": xform.num_of_submissions,
                            "email": xform.user.email,
                            "id_string": xform.id_string
                        }]
                    else:
                        duplicates_dict[xform.user].append({
                            "form id": xform.pk,
                            "no. of submission": xform.num_of_submissions,
                            "email": xform.user.email,
                            "id_string": xform.id_string
                        })
            self.stdout.write(
                'Accounts with duplicate id_strings: %s' %
                len(duplicates_dict))
            pprint(duplicates_dict)
        else:
            self.stdout.write('Each account has a unique id_string :)')
