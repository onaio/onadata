#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=5
# -*- coding: utf-8 -*-
"""
import_instances - import ODK instances from a zipped file.
"""
import os


from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from onadata.apps.logger.import_tools import (
    import_instances_from_path,
    import_instances_from_zip,
)

# pylint: disable=invalid-name
User = get_user_model()


class Command(BaseCommand):
    """
    import_instances - import ODK instances from a zipped file.
    """

    help = gettext_lazy(
        "Import a zip file, a directory containing zip files "
        "or a directory of ODK instances"
    )

    def add_arguments(self, parser):
        parser.add_argument("username", type=str)
        parser.add_argument("path", type=str)

    def _log_import(self, results):
        total_count, success_count, errors = results
        self.stdout.write(
            _(
                "Total: %(total)d, Imported: %(imported)d, Errors: "
                "%(errors)s\n------------------------------\n"
            )
            % {"total": total_count, "imported": success_count, "errors": errors}
        )

    # pylint: disable=unused-argument
    def handle(self, *args, **kwargs):
        username = kwargs["username"]
        path = kwargs["path"]
        is_async = False
        if len(args) > 2:
            if isinstance(args[2], str):
                is_async = args[2].lower() == "true"

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as e:
            raise CommandError(
                _(f"The specified user '{username}' does not exist.")
            ) from e

        # make sure path exists
        if not os.path.exists(path):
            raise CommandError(_(f"The specified path '{path}' does not exist."))
        for directory, subdirs, files in os.walk(path):
            # check if the directory has an odk directory
            if "odk" in subdirs:
                # dont walk further down this directory
                subdirs.remove("odk")
                self.stdout.write(_(f"Importing from directory {directory}..\n"))
                results = import_instances_from_path(directory, user, is_async=is_async)
                self._log_import(results)
            for file in files:
                filepath = os.path.join(path, file)
                is_zip_file = (
                    os.path.isfile(filepath)
                    and os.path.splitext(filepath)[1].lower() == ".zip"
                )
                if is_zip_file:
                    self.stdout.write(_(f"Importing from zip at {filepath}..\n"))
                    results = import_instances_from_zip(filepath, user)
                    self._log_import(results)
