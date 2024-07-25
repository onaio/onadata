#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8
# -*- coding: utf-8 -*-
"""
update_xform_uuids command - Set uuid from a CSV file
"""

import csv

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext_lazy

from onadata.apps.logger.models.xform import (
    DuplicateUUIDError,
    XForm,
    update_xform_uuid,
)


class Command(BaseCommand):
    """Use a csv file with username, id_string and new_uuid to set new uuids."""

    help = gettext_lazy(
        "Use a csv file with username, id_string and new_uuid to set new uuids"
    )

    def add_arguments(self, parser):
        parser.add_argument("-f", "--file", help=gettext_lazy("Path to csv file"))

    def handle(self, *args, **kwargs):
        """Use a csv file with username, id_string and new_uuid to set new uuids."""
        # all options are required
        if not kwargs.get("file"):
            raise CommandError("You must provide a path to the csv file")
        # try open the file
        try:
            with open(kwargs.get("file"), "r", encoding="utf-8") as csv_file:
                lines = csv.reader(csv_file)
                i = 0
                for line in lines:
                    try:
                        username = line[0]
                        id_string = line[1]
                        uuid = line[2]
                        update_xform_uuid(username, id_string, uuid)
                    except IndexError:
                        self.stderr.write(f"line {i + 1} is in an invalid format")
                    except XForm.DoesNotExist:
                        self.stderr.write(
                            f"XForm with username: {username} and id "
                            f"string: {id_string} does not exist"
                        )
                    except DuplicateUUIDError:
                        self.stderr.write(f"An xform with uuid: {uuid} already exists")
                    else:
                        i += 1
                        self.stdout.write(f"Updated {i} rows")
        except IOError as error:
            raise CommandError(
                f"file {kwargs.get('file')} could not be open"
            ) from error
