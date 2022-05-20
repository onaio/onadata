#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
import_briefcase command

- imports XForm XML from a folder and publishes the XForm.
- import XForm submissions XML from a folder and inserts into the table instances.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from onadata.libs.utils.briefcase_client import BriefcaseClient


class Command(BaseCommand):
    """Insert all existing parsed instances into MongoDB"""

    help = _("Insert all existing parsed instances into MongoDB")

    def add_arguments(self, parser):
        parser.add_argument("--url", help=_("server url to pull forms and submissions"))
        parser.add_argument("-u", "--username", help=_("Username"))
        parser.add_argument("-p", "--password", help=_("Password"))
        parser.add_argument("--to", help=_("username in this server"))

    def handle(self, *args, **options):
        """Insert all existing parsed instances into MongoDB"""
        url = options.get("url")
        username = options.get("username")
        password = options.get("password")
        user = get_user_model().objects.get(username=options.get("to"))
        client = BriefcaseClient(
            username=username, password=password, user=user, url=url
        )
        client.push()
