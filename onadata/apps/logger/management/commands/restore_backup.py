# -*- coding: utf-8 -*-
"""
restore_backup command - Restore a zip backup of a form and all its submissions
"""
import os
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext_lazy, gettext as _

from onadata.libs.utils.backup_tools import restore_backup_from_zip


class Command(BaseCommand):
    """
    restore_backup command - Restore a zip backup of a form and all its submissions
    """

    args = "username input_file"
    help = gettext_lazy("Restore a zip backup of a form and all its submissions")

    def handle(self, *args, **options):
        # pylint: disable=invalid-name
        User = get_user_model()
        try:
            username = args[0]
        except IndexError:
            raise CommandError(
                _("You must provide the username to publish the form to.")
            )
            # make sure user exists
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(_(f"The user '{username}' does not exist."))

        try:
            input_file = args[1]
        except IndexError:
            raise CommandError(_("You must provide the path to restore from."))
        else:
            input_file = os.path.realpath(input_file)

        num_instances, num_restored = restore_backup_from_zip(input_file, username)
        sys.stdout.write(f"Restored {num_restored} of {num_instances } submissions\n")
