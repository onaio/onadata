# -*- coding: utf-8 -*-
"""
get_accounts_with_duplicate_id_strings - Retrieves accounts with duplicate id_strings
"""
from pprint import pprint

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils.translation import gettext_lazy

from onadata.apps.logger.models.xform import XForm


class Command(BaseCommand):
    """Retrieves accounts with duplicate id_strings"""

    help = gettext_lazy("Retrieves accounts with duplicate id_strings")

    # pylint: disable=unused-argument
    def handle(self, *args, **kwargs):
        """Retrieves accounts with duplicate id_strings"""
        duplicates = (
            XForm.objects.values("id_string", "user__username")
            .annotate(id_string_count=Count("id_string"))
            .filter(id_string_count__gt=1)
        )
        duplicates_dict = {}
        if len(duplicates) > 0:
            for dupe in duplicates:
                xforms = XForm.objects.filter(
                    id_string=dupe.get("id_string"),
                    user__username=dupe.get("user__username"),
                )
                for xform in xforms:
                    if duplicates_dict.get(xform.user) is None:
                        duplicates_dict[xform.user] = [
                            {
                                "form id": xform.pk,
                                "no. of submission": xform.num_of_submissions,
                                "email": xform.user.email,
                                "id_string": xform.id_string,
                            }
                        ]
                    else:
                        duplicates_dict[xform.user].append(
                            {
                                "form id": xform.pk,
                                "no. of submission": xform.num_of_submissions,
                                "email": xform.user.email,
                                "id_string": xform.id_string,
                            }
                        )
            self.stdout.write(
                f"Accounts with duplicate id_strings: {len(duplicates_dict)}"
            )
            pprint(duplicates_dict)
        else:
            self.stdout.write("Each account has a unique id_string :)")
