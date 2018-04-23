#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8

import csv

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext_lazy

from onadata.apps.logger.models.xform import (DuplicateUUIDError, XForm,
                                              update_xform_uuid)


class Command(BaseCommand):
    help = ugettext_lazy(
        "Use a csv file with username, id_string and new_uuid to set new"
        " uuids")

    def add_arguments(self, parser):
        parser.add_argument(
            '-f', '--file', help=ugettext_lazy("Path to csv file"))

    def handle(self, *args, **kwargs):
        # all options are required
        if not kwargs.get('file'):
            raise CommandError("You must provide a path to the csv file")
        # try open the file
        try:
            with open(kwargs.get('file'), "r") as f:
                lines = csv.reader(f)
                i = 0
                for line in lines:
                    try:
                        username = line[0]
                        id_string = line[1]
                        uuid = line[2]
                        update_xform_uuid(username, id_string, uuid)
                    except IndexError:
                        self.stderr.write(
                            "line %d is in an invalid format" % (i + 1))
                    except XForm.DoesNotExist:
                        self.stderr.write("XForm with username: %s and id "
                                          "string: %s does not exist"
                                          % (username, id_string))
                    except DuplicateUUIDError:
                        self.stderr.write(
                            "An xform with uuid: %s already exists" % uuid)
                    else:
                        i += 1
                        self.stdout.write("Updated %d rows" % i)
        except IOError:
            raise CommandError(
                "file %s could not be open" % kwargs.get('file'))
