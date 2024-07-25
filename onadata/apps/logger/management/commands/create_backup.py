# -*- coding: utf-8 -*-
"""
create_backup - command to create zipped backup of a form and it's submissions.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from onadata.apps.logger.models import XForm
from onadata.libs.utils.backup_tools import create_zip_backup


class Command(BaseCommand):
    """Create a zip backup of a form and all its submissions."""

    args = "outfile username [id_string]"
    help = gettext_lazy("Create a zip backup of a form and all its submissions")

    # pylint: disable=unused-argument
    def handle(self, *args, **options):  # noqa C901
        """Create a zip backup of a form and all its submissions."""
        try:
            output_file = args[0]
        except IndexError as error:
            raise CommandError(
                _("Provide the path to the zip file to backup to")
            ) from error
        output_file = os.path.realpath(output_file)

        try:
            username = args[1]
        except IndexError as error:
            raise CommandError(
                _("You must provide the username to publish the form to.")
            ) from error
        # make sure user exists
        try:
            user = get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist as error:
            raise CommandError(_(f"The user '{username}' does not exist.")) from error

        try:
            id_string = args[2]
        except IndexError:
            xform = None
        else:
            # make sure xform exists
            try:
                xform = XForm.objects.get(user=user, id_string=id_string)
            except XForm.DoesNotExist as error:
                raise CommandError(
                    _(f"The id_string '{id_string}' does not exist.")
                ) from error
        create_zip_backup(output_file, user, xform)
