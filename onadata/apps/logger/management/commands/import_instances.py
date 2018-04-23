#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=5 coding=utf-8
import os

from past.builtins import basestring

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from onadata.apps.logger.import_tools import (import_instances_from_path,
                                              import_instances_from_zip)


class Command(BaseCommand):
    args = 'username path'
    help = ugettext_lazy("Import a zip file, a directory containing zip files "
                         "or a directory of ODK instances")

    def _log_import(self, results):
        total_count, success_count, errors = results
        self.stdout.write(_(
            "Total: %(total)d, Imported: %(imported)d, Errors: "
            "%(errors)s\n------------------------------\n") % {
            'total': total_count, 'imported': success_count,
            'errors': errors})

    def handle(self, *args, **kwargs):
        if len(args) < 2:
            raise CommandError(_("Usage: <command> username file/path."))
        username = args[0]
        path = args[1]
        is_async = args[2] if len(args) > 2 else False
        is_async = True if isinstance(is_async, basestring) and \
            is_async.lower() == 'true' else False
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(_(
                "The specified user '%s' does not exist.") % username)

        # make sure path exists
        if not os.path.exists(path):
            raise CommandError(_(
                "The specified path '%s' does not exist.") % path)

        for dir, subdirs, files in os.walk(path):
            # check if the dir has an odk directory
            if "odk" in subdirs:
                # dont walk further down this dir
                subdirs.remove("odk")
                self.stdout.write(_("Importing from dir %s..\n") % dir)
                results = import_instances_from_path(
                    dir, user, is_async=is_async
                )
                self._log_import(results)
            for file in files:
                filepath = os.path.join(path, file)
                if os.path.isfile(filepath) and\
                        os.path.splitext(filepath)[1].lower() == ".zip":
                    self.stdout.write(_(
                        "Importing from zip at %s..\n") % filepath)
                    results = import_instances_from_zip(filepath, user)
                    self._log_import(results)
